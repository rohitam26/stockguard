# StockGuard Architecture Specification

## 1. System Overview

StockGuard is an enterprise distributed inventory control and saga orchestration platform built to guarantee high-concurrency consistency, atomic stock reservations without race conditions, and reliable event-driven state propagation.

```
                           +----------------------------+
                           |     FastAPI Gateway        |
                           |  (REST API & Web UI)       |
                           +--------------+-------------+
                                          |
                +-------------------------+-------------------------+
                |                         |                         |
       +--------v-------+        +--------v-------+        +--------v-------+
       |   Inventory    |        |   Reservation  |        |     Order      |
       |    Service     |        |     Engine     |        |    Service     |
       +--------+-------+        +--------+-------+        +--------+-------+
                |                         |                         |
                +-------------------------+-------------------------+
                                          |
                               +----------v----------+
                               |  Saga Orchestrator  |
                               +----+-----------+----+
                                    |           |
                           +--------v----+ +----v--------+
                           |   Payment   | | Fulfillment |
                           |  Simulator  | |   Service   |
                           +-------------+ +-------------+
                                    |           |
            +-----------------------+-----------+-----------------------+
            |                                                           |
   +--------v--------+                                         +--------v--------+
   | PostgreSQL 16   |                                         |  RabbitMQ Broker|
   | - Row Locking   |                                         |  - Topic Exch   |
   | - Check Constr  |                                         |  - DLQ Routing  |
   | - Outbox Table  | === Polled by Outbox Worker ===========>|  - At-Least-Once|
   +-----------------+                                         +-----------------+
```

## 2. Concurrency Control & Overselling Prevention

To guarantee that inventory never drops below zero and overselling is mathematically prevented under extreme traffic spikes:

1. **Database-Level CHECK Constraints:**
   - `chk_inventory_available_non_negative`: `CHECK (available_stock >= 0)`
   - `chk_inventory_reserved_non_negative`: `CHECK (reserved_stock >= 0)`
   - `chk_inventory_allocated_non_negative`: `CHECK (allocated_stock >= 0)`

2. **Atomic Conditional SQL Decrement:**
   ```sql
   UPDATE inventory_items
   SET available_stock = available_stock - :requested_qty,
       reserved_stock = reserved_stock + :requested_qty,
       version = version + 1
   WHERE sku = :sku AND available_stock >= :requested_qty;
   ```
   If `available_stock < :requested_qty`, `rowcount == 0` and the transaction immediately raises `InsufficientStockException`. No lock escalations or phantom read vulnerabilities.

3. **Client Idempotency:**
   Every reservation requires an `idempotency_key`. The `reservations` table enforces a unique constraint on `idempotency_key`. Subsequent identical requests return the active reservation without redundant inventory deductions.

## 3. Distributed Saga Orchestration & Compensation

Orders coordinate across Inventory, Payment, and Fulfillment via an orchestrator executing backward compensation:

1. **Step 1 (Reservation):**
   - For each order item, acquires an atomic reservation.
   - *Failure Compensation:* If any item has insufficient stock, releases all reservations acquired for previous items in that order. Order marked `FAILED`.

2. **Step 2 (Payment):**
   - Payment simulated (deterministic or simulated failure).
   - *Failure Compensation:* If payment is declined, the orchestrator triggers automated compensation releasing all acquired reservations back to `available_stock`. Order marked `CANCELLED`.

3. **Step 3 (Fulfillment):**
   - Upon payment confirmation, reservations transition to `CONFIRMED`.
   - Reserved stock is transferred to `allocated_stock`.
   - Fulfillment tracking initiated (`PACKING` -> `SHIPPED` -> `DELIVERED`).
   - Order marked `COMPLETED`.

## 4. Transactional Outbox Pattern

To eliminate dual-write discrepancies between the PostgreSQL database and the RabbitMQ message broker:

- Domain modifications and domain events write to the `outbox_messages` table within the **same local database transaction**.
- A decoupled `OutboxWorker` reads pending messages, publishes them with `delivery_mode=2` (Persistent) to `stockguard.topic`, and marks the outbox status as `PUBLISHED`.
- If the broker is momentarily unavailable, messages remain safely staged in `outbox_messages` with retry counters and dead-letter queue routing.
- Consumers utilize the `processed_events` table for message deduplication.
