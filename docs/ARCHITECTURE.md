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

## 5. Security & Identity Architecture

StockGuard implements defense-in-depth API security:
1. **JWT Authentication & Token Lifecycle:**
   - Stateless JWT access tokens signed with HMAC-SHA256 (30-minute expiration).
   - Stateful refresh tokens stored as SHA-256 hashes in `refresh_tokens`. Every refresh triggers **token rotation** and revocation of prior tokens, preventing replay attacks.
2. **Password Hashing:**
   - Handled via `bcrypt` (12 rounds) with Argon2 verification compatibility.
   - Plaintext passwords and tokens are never persisted or exposed in application logs.
3. **Role-Based Access Control (RBAC):**
   - Fine-grained role hierarchy (`ADMIN`, `INVENTORY_MANAGER`, `CUSTOMER`, `SERVICE`).
   - Least-privilege validation enforced at the API boundary via FastAPI dependencies (`require_role`).
4. **IDOR Prevention:**
   - Resource ownership checks (`check_resource_ownership`) verify customer ownership of orders and reservations.
5. **Sliding-Window Rate Limiting:**
   - `InMemoryRateLimiter` enforces rate boundaries on `/auth/*` and sensitive endpoints, responding with HTTP 429 and `Retry-After` headers.

## 6. Outbox Concurrency & Crash Recovery

1. **`FOR UPDATE SKIP LOCKED`:**
   - Multiple background outbox workers safely poll pending messages concurrently without double-publishing.
2. **Stuck Event Recovery:**
   - Messages left in `PROCESSING` status for over 60 seconds (due to unexpected process termination or network drops) are automatically recovered by `recover_stuck_messages()` and restored to `PENDING`.
3. **Poison Message Quarantine:**
   - Messages with corrupt or unparseable payloads are immediately isolated to `FAILED` status, logging the root cause without crashing workers or blocking healthy messages.

## 7. Observability & Telemetry

1. **Correlation IDs & Request Tracing:**
   - `ObservabilityMiddleware` assigns or propagates `X-Correlation-ID` across inbound requests and downstream logs.
   - Optional distributed tracing via OpenTelemetry (`opentelemetry-instrumentation-fastapi`).
2. **Prometheus Metrics Exposition:**
   - Metrics available at `/metrics` and `/api/v1/health/metrics` covering request throughput, P50/P95 latencies, reservation outcomes, and outbox backlog gauges.
3. **Kubernetes Health Probes:**
   - `/api/v1/health/live` (process liveness).
   - `/api/v1/health/ready` (PostgreSQL connectivity check).

## 8. Architecture Decision Records (ADRs)

Key architectural trade-offs are documented in [`docs/adr/`](adr/):
- **[ADR 001: Modular Monolith with Decoupled Entrypoints](adr/001-modular-monolith-vs-microservices.md)**
- **[ADR 002: Transactional Outbox Pattern vs Dual Writes](adr/002-transactional-outbox-vs-dual-writes.md)**
- **[ADR 003: Pessimistic Row Locking vs Distributed Locks](adr/003-pessimistic-locking-vs-optimistic-concurrency.md)**
- **[ADR 004: Orchestrator-Driven Saga vs Event Choreography](adr/004-saga-orchestration-vs-choreography.md)**
- **[ADR 005: JWT Authentication, RBAC & Refresh Token Rotation](adr/005-jwt-rbac-refresh-token-rotation.md)**
