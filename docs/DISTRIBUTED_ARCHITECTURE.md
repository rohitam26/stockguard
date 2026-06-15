# StockGuard Distributed Architecture & Service Decomposition

## 1. Architectural Baseline: Modular Monolith

Currently, StockGuard operates as a **Modular Monolith**:
- All four core business services (**Inventory**, **Order**, **Payment**, **Fulfillment**) are structured into distinct service modules with clear domain model boundaries, explicit Pydantic contract schemas, and isolated database tables.
- In development and standard deployment, they execute within a unified FastAPI process (`stockguard.main:app`), communicating via direct in-process method invocation and publishing asynchronous domain events to the **Transactional Outbox**.
- A unified PostgreSQL 16 database holds separate domain tables for each service, avoiding cross-service database JOINs where possible.

### Architecture Strengths
1. **Low Operational Overhead:** Single application lifecycle, unified logging, and simple local execution.
2. **Transactional Consistency:** Database-level atomicity across related tables (e.g., inventory reservation and outbox staging).
3. **High Performance:** Microsecond in-process invocation during high contention without HTTP network serialization overhead.

---

## 2. Service Separation & Independent Deployability Analysis

To support independent scaling, separate deployment pipelines, and failure isolation, StockGuard provides decoupled microservice entrypoints:

| Service | Primary Domain Responsibility | Independent Entrypoint | Default Port |
| :--- | :--- | :--- | :--- |
| **Inventory Service** | Products, Available/Reserved Stock, Atomic Reservations | `stockguard.microservices.inventory_service_app:app` | `8001` |
| **Order Service** | Customer Orders, Checkout State Machine, Saga Orchestrator | `stockguard.microservices.order_service_app:app` | `8002` |
| **Payment Service** | Payment Gateway Simulation, Authorization Records | `stockguard.microservices.payment_service_app:app` | `8003` |
| **Fulfillment Service**| Packaging, Carrier Tracking Numbers, Shipping States | `stockguard.microservices.fulfillment_service_app:app` | `8004` |
| **Unified Monolith / Gateway** | Dashboard UI, Aggregated Health, Static Web Assets | `stockguard.main:app` | `8000` |

---

## 3. Explicit Inter-Service Contracts

All inter-service interactions are strictly governed by explicit Pydantic schemas:

### A. Inventory Contracts
- **`ReservationCreateRequest`:** `{ sku: str, quantity: int, ttl_seconds: int, idempotency_key: str }`
- **`ReservationResponse`:** `{ id: str, sku: str, quantity: int, status: str, expires_at: datetime }`
- **`ReservationReleaseRequest`:** Triggered during Saga compensation.

### B. Order Contracts
- **`OrderCreateRequest`:** `{ customer_id: str, items: list[OrderItemCreate] }`
- **`OrderResponse`:** `{ id: str, customer_id: str, status: OrderStatus, total_amount: float }`

### C. Payment Contracts
- **`PaymentCreateRequest`:** `{ order_id: str, amount: float, idempotency_key: str, simulate_failure: bool }`
- **`PaymentResponse`:** `{ id: str, order_id: str, status: PaymentStatus, transaction_id: str }`

### D. Fulfillment Contracts
- **`FulfillmentInitiateRequest`:** `{ order_id: str, tracking_number: str }`
- **`FulfillmentResponse`:** `{ id: str, order_id: str, status: FulfillmentStatus, tracking_number: str }`

---

## 4. Saga Orchestration Evolution: In-Process vs Choreographed

Currently, `SagaOrchestrator` uses **Orchestrator-driven execution**:
1. Order Service initiates Saga on `/checkout`.
2. Steps execute sequentially (Reservation -> Payment -> Fulfillment).
3. On payment error, Order Service coordinates rollback by issuing `release_reservation` calls.

### Microservices Evolution Path
When deployed as decoupled microservices across network boundaries:
1. **HTTP/REST Orchestration:** The Order Service calls the external HTTP endpoints (`http://inventory-service:8001/api/v1/reservations`, etc.).
2. **Choreographed AMQP (Event-Driven):**
   - Order Service emits `OrderCreated` to RabbitMQ `stockguard.orders`.
   - Inventory Consumer listens, acquires reservation, emits `InventoryReserved` or `ReservationFailed`.
   - Payment Consumer listens to `InventoryReserved`, charges customer, emits `PaymentSucceeded` or `PaymentFailed`.
   - Fulfillment Consumer listens to `PaymentSucceeded`, generates tracking number.
   - If `PaymentFailed` is emitted, Inventory Consumer listens and compensates by releasing reserved stock.

This architecture preserves zero dual-write loss via the **Transactional Outbox Pattern** across all stages.
