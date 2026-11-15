# StockGuard: Enterprise Distributed Inventory & Saga Engine

[![StockGuard CI](https://github.com/example/stockguard/actions/workflows/ci.yml/badge.svg)](https://github.com/example/stockguard/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

StockGuard is a high-performance distributed inventory management and checkout coordination engine. Built for high-contention e-commerce flash sales, it guarantees zero overselling, atomic reservations without race conditions, transactional outbox event delivery, and distributed saga orchestration with automatic backward compensation.

---

## Application Showcase

### 1. Enterprise Dashboard Overview
Live inventory levels, active reservation countdowns, low-stock threshold monitoring, and PostgreSQL 16 engine connectivity.
![Dashboard Overview](docs/screenshots/01_dashboard_overview.png)

### 2. Distributed Saga Orchestrator & Compensation
Interactive multi-step order checkout showing atomic inventory reservation, payment debit, fulfillment dispatch, and automated backward compensation on payment failure.
![Saga Visualizer](docs/screenshots/02_order_saga_visualizer.png)

### 3. Atomic Reservations & Idempotency
Client-supplied idempotency key verification preventing duplicate allocations, with background auto-expiry sweep.
![Atomic Reservations](docs/screenshots/03_atomic_reservations.png)

### 4. Transactional Outbox & Event Streaming
Guaranteed event publication without dual-write inconsistencies or message loss.
![Transactional Outbox](docs/screenshots/04_transactional_outbox.png)

### 5. Interactive OpenAPI / Swagger Documentation
Full REST API explorer with request/response schemas.
![Swagger Documentation](docs/screenshots/05_swagger_api_docs.png)

---

## Screenshot Index

| Filename | Feature / Page | Capture Date | Tested |
| :--- | :--- | :--- | :--- |
| [`01_dashboard_overview.png`](docs/screenshots/01_dashboard_overview.png) | Dashboard Overview & Live Inventory Table | 2026-11-15 | Yes |
| [`02_order_saga_visualizer.png`](docs/screenshots/02_order_saga_visualizer.png) | Saga Checkout Stepper & Compensation Log | 2026-11-15 | Yes |
| [`03_atomic_reservations.png`](docs/screenshots/03_atomic_reservations.png) | Atomic Reservation Engine & Idempotency Form | 2026-11-15 | Yes |
| [`04_transactional_outbox.png`](docs/screenshots/04_transactional_outbox.png) | Transactional Outbox Log & Worker Dispatcher | 2026-11-15 | Yes |
| [`05_swagger_api_docs.png`](docs/screenshots/05_swagger_api_docs.png) | Interactive Swagger API Documentation | 2026-11-15 | Yes |

---

## Architectural Highlights

```
                       +----------------------------+
                       |      FastAPI Gateway       |
                       |    (REST API & Web UI)     |
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
+-------v---------+                                         +-------v---------+
| PostgreSQL 16   |                                         |  RabbitMQ Broker|
| - Row-Level Lock|                                         |  - Topic Exch   |
| - CHECK Constr  |                                         |  - DLQ Routing  |
| - Outbox Table  | === Polled by Outbox Worker ===========>|  - At-Least-Once|
+-----------------+                                         +-----------------+
```

### 1. Concurrency Control & Overselling Prevention
- **Database CHECK Constraints:** PostgreSQL strictly enforces `CHECK (available_stock >= 0)`.
- **Atomic Conditional SQL Decrement:**
  ```sql
  UPDATE inventory_items
  SET available_stock = available_stock - :qty,
      reserved_stock = reserved_stock + :qty,
      version = version + 1
  WHERE sku = :sku AND available_stock >= :qty;
  ```
  If stock is insufficient, the row count is `0` and an `InsufficientStockException` is raised immediately.

### 2. Verified 100-Request Concurrency Scenario
In accordance with system audit requirements, a stress test was executed directly against **PostgreSQL 16**:
- **Setup:** 5 units of stock available for SKU `CONCURRENCY-5-100`.
- **Stimulus:** 100 concurrent requests issued simultaneously via 20 worker threads.
- **Result:**
  - Exactly **5 requests succeeded** (201 Created).
  - Exactly **95 requests were rejected** with 409 Conflict.
  - Final PostgreSQL stock: `available = 0`, `reserved = 5`, `allocated = 0`, `total = 5`.
  - Negative inventory prevented with zero data anomalies.

### 3. Distributed Saga Backward Compensation
If payment fails or partial inventory cannot be fulfilled:
1. Acquired reservations are atomically released back to `available_stock`.
2. Order status transitions to `CANCELLED` or `FAILED`.
3. Outbox event `reservation.released` is emitted.
4. Zero orphan stock locks remain.

### 4. Transactional Outbox Pattern
Domain mutations and event messages write to `outbox_messages` in the same DB transaction. A dedicated `OutboxWorker` dispatches events to RabbitMQ with retry policies and Dead Letter Queue (`stockguard.dlq`) routing.

---

## Quickstart & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16
- RabbitMQ 3.13 (optional, fallback in-memory bus included)

### 1. Clone & Install
```bash
git clone https://github.com/example/stockguard.git
cd stockguard
python -m pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment
Copy and adjust `.env`:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stockguard
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_ENABLED=true
ENVIRONMENT=development
```

### 3. Database Migration
```bash
python -m alembic upgrade head
```

### 4. Run Server
```bash
uvicorn stockguard.main:app --host 0.0.0.0 --port 8000 --reload
```
Access the Dashboard at: [http://localhost:8000](http://localhost:8000)  
Access Swagger API Docs at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Docker Compose Deployment
```bash
docker compose up --build
```

---

## Automated Test Suite

Run the full pytest suite (including PostgreSQL concurrency and failure recovery tests):
```bash
python -m pytest -v -s
```

Run load and latency benchmarks:
```bash
python scripts/benchmark_load_test.py
```

Run dependency vulnerability audit:
```bash
python -m pip_audit -r requirements.txt
```

---

## Documentation
- [Final Project Audit Report](docs/FINAL_AUDIT_REPORT.md)
- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Security Policy & Findings](docs/SECURITY.md)
- [Changelog](CHANGELOG.md)

---

## License
MIT License. Copyright (c) 2026 StockGuard Engineering Team.
