# StockGuard Production Reliability Engineering Guide

This document defines the reliability engineering principles, distributed systems patterns, fault recovery guarantees, and operational procedures implemented within StockGuard.

---

## 1. Zero Overselling Guarantees

E-commerce flash sales produce extreme write contention on limited inventory. StockGuard prevents overselling through three mutually reinforcing defensive layers:

```
[ Incoming Reservation Request ]
               |
               v
  Layer 1: Input Validation (Pydantic)
  - quantity > 0
  - non-empty SKU
               |
               v
  Layer 2: Atomic Conditional SQL (PostgreSQL)
  - UPDATE inventory_items
    SET available_stock = available_stock - :qty,
        reserved_stock = reserved_stock + :qty
    WHERE sku = :sku AND available_stock >= :qty
  - If rowcount == 0 -> InsufficientStockException (HTTP 409)
               |
               v
  Layer 3: Database Engine CHECK Constraint
  - CHECK (available_stock >= 0)
  - Enforced by PostgreSQL relational storage engine
```

### Empirical Verification
- Tested with 100 concurrent requests across 20 worker threads against 5 physical units in PostgreSQL.
- Exactly 5 succeeded, 95 were rejected with HTTP 409 Conflict.
- Final database inventory: `available_stock = 0`, `reserved_stock = 5`, `allocated_stock = 0`. Negative stock was completely prevented.

---

## 2. Idempotency & Duplicate Request Protection

Network timeouts and user retry behaviors frequently produce duplicate submissions. StockGuard provides end-to-end idempotency:

1. **Client-Supplied Idempotency Keys:** Every reservation (`idempotency_key`) and order creation requires an idempotency identifier. Subsequent requests with identical keys return the existing record without duplicating stock deductions.
2. **Checkout Idempotency:** The Saga orchestrator inspects order terminal state. Calling checkout on an already completed order returns the existing completion state rather than re-initiating reservations or charges.
3. **Consumer Deduplication:** RabbitMQ workers record message processing keys in the `processed_events` PostgreSQL table (`event_key = message_id:consumer_name`). Duplicate deliveries are acknowledged and skipped.

---

## 3. RabbitMQ Reliability Engineering

```
[ Domain Mutation + Outbox Record ] (Atomic DB Transaction)
               |
               v
     [ Transactional Outbox ]
               |
               v (FOR UPDATE SKIP LOCKED)
      [ Outbox Worker ]
               |
               v (Publisher Confirms + Persistent Delivery)
     [ RabbitMQ Topic Exchange: stockguard.topic ]
        /             |             \
 [ stockguard.inv ] [ orders ] [ payments ]
        |
    (Error / Requeue Limit)
        |
        v
 [ DLX: stockguard.dlq ]
        |
        v
 [ stockguard.dlq.queue ]
```

- **Durable Infrastructure:** Exchanges and queues are declared with `durable=True`.
- **Persistent Messages:** Dispatched with `delivery_mode=pika.DeliveryMode.Persistent`.
- **Publisher Confirms:** Channels enable `confirm_delivery()` guaranteeing messages are persisted by RabbitMQ before being marked published.
- **Manual Acknowledgement:** Consumers acknowledge with `basic_ack()` only after the database transaction commits.
- **Dead Letter Routing:** Corrupt or poison messages trigger `basic_nack(requeue=False)` routing to `stockguard.dlq`.
- **In-Memory Fallback:** When RabbitMQ is offline in local development, traffic gracefully routes through an internal in-memory event bus with zero operational disruption.

---

## 4. Transactional Outbox & Worker Crash Recovery

- **Single Transaction Boundaries:** Entity modifications and outbox records are committed in the exact same database transaction.
- **Concurrency Protection:** Workers poll using PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`. Multiple workers running in parallel claim disjoint sets of messages without contention or duplication.
- **Stuck Message Recovery:** If a worker process is terminated mid-flight, messages remaining in `PROCESSING` status for over 60 seconds are automatically identified by `recover_stuck_messages()` and restored to `PENDING`.
- **Poison Event Quarantine:** Unparseable JSON payloads are quarantined immediately to `FAILED` status, preventing infinite processing crash loops.
