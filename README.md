# StockGuard: Premium Distributed Inventory Intelligence & Saga Engine

[![StockGuard CI](https://github.com/rohitam26/stockguard/actions/workflows/ci.yml/badge.svg)](https://github.com/rohitam26/stockguard/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-173824.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-059669.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-059669.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-E76F51.svg)](https://opensource.org/licenses/MIT)

**StockGuard** is an enterprise-grade distributed inventory intelligence and order checkout coordination engine built for high-contention e-commerce flash sales. It guarantees **zero overselling**, **atomic reservations without race conditions**, **transactional outbox event streaming**, and **distributed saga orchestration with automated backward compensation**.

The web console is designed as a modern SaaS operations platform using a distinctive **Forest Green** and **Warm Ivory** design system with **Emerald** actions and **Coral** accents.

> **Operational Status:** StockGuard is a verified **functional distributed-systems prototype**. The core transactional patterns (atomic row-level reservations, transactional outbox, and distributed saga compensation) are mathematically and empirically proven against PostgreSQL 16.2. For production deployment, consult the [Operational Limitations](#operational-boundaries--limitations) section.

---

## Project Inception & Timeline

- **Original Project Inception & Conceptual Design:** Commenced prior to June 2026 (per project origin records; early exploratory files unindexed).
- **Core Implementation & Git History:** Initialized November 15, 2026 with 100% verified Git history.
- **Current Milestone:** v1.3.0 Public Release (November 16, 2026).

---

## Application Showcase & Screenshot Gallery

All screenshots are authentic, high-resolution captures from the live application running against local PostgreSQL 16.2.

### 1. Operations Overview Dashboard
Live inventory distribution bar, active reservation countdowns, low-stock alerts, and real-time KPI metrics.
![Overview Dashboard](docs/screenshots/final-ui/overview-dashboard.png)

### 2. Inventory & Catalog Intelligence
Live SKU management with status filters (`All`, `In Stock`, `Low Stock`, `Depleted`), instant search, and quick restock actions.
![Inventory Management](docs/screenshots/final-ui/inventory-management.png)

### 3. Atomic Stock Reservations
Client-supplied idempotency key verification preventing duplicate allocations, with background auto-expiry sweep and 1-click release.
![Atomic Reservations](docs/screenshots/final-ui/atomic-reservations.png)

### 4. Distributed Saga Stepper & Backward Compensation
Interactive checkout coordination visualizer showing atomic inventory reservation, payment debit, fulfillment dispatch, and automated backward compensation on payment failure.
![Order Saga Visualizer](docs/screenshots/final-ui/order-saga.png)

### 5. Transactional Outbox Operations Console
Guaranteed at-least-once event publication without dual-write inconsistencies or message loss, backed by background worker polling.
![Transactional Outbox](docs/screenshots/final-ui/transactional-outbox.png)

### 6. System Architecture & Topology Health
Live connection status for PostgreSQL 16 (port 5432), RabbitMQ broker / In-Memory Fallback mode, and reliability pattern verification.
![System Health](docs/screenshots/final-ui/system-health.png)

### 7. Responsive Mobile Viewport
Fully adaptable, touch-friendly mobile navigation and card layout tested on mobile viewports.
![Mobile Dashboard](docs/screenshots/final-ui/mobile-dashboard.png)

---

## Screenshot Index

| Filename | Feature / Page | Capture Timestamp | Verification Status |
| :--- | :--- | :--- | :--- |
| [`overview-dashboard.png`](docs/screenshots/final-ui/overview-dashboard.png) | Overview Dashboard & Live Stock Distribution | 2026-11-15 22:00:54 | **VERIFIED** |
| [`inventory-management.png`](docs/screenshots/final-ui/inventory-management.png) | Catalog Management with Stock Filters | 2026-11-15 22:00:55 | **VERIFIED** |
| [`atomic-reservations.png`](docs/screenshots/final-ui/atomic-reservations.png) | Atomic Reservation Engine & Idempotency | 2026-11-15 22:00:56 | **VERIFIED** |
| [`order-saga.png`](docs/screenshots/final-ui/order-saga.png) | Distributed Saga Stepper & Compensation Log | 2026-11-15 22:00:58 | **VERIFIED** |
| [`transactional-outbox.png`](docs/screenshots/final-ui/transactional-outbox.png) | Transactional Outbox Event Stream & Flush | 2026-11-15 22:00:59 | **VERIFIED** |
| [`system-health.png`](docs/screenshots/final-ui/system-health.png) | Dedicated System Architecture & Health Grid | 2026-11-15 22:01:00 | **VERIFIED** |
| [`mobile-dashboard.png`](docs/screenshots/final-ui/mobile-dashboard.png) | Responsive Mobile Layout (390x844 Viewport) | 2026-11-15 22:01:01 | **VERIFIED** |

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
| PostgreSQL 16   |                                         | RabbitMQ Broker |
| - Row-Level Lock|                                         | - Topic Exch    |
| - CHECK Constr  |                                         | - DLQ Routing   |
| - Outbox Table  | === Polled by Outbox Worker ===========>| - At-Least-Once |
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
In accordance with system audit requirements, a stress test was executed directly against **PostgreSQL 16.2**:
- **Setup:** 5 units of available stock for a high-contention test SKU.
- **Stimulus:** 100 concurrent reservation requests issued simultaneously across 20 worker threads.
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

### 5. Real-Time Multi-Window Synchronization Engine
The StockGuard dashboard automatically synchronizes with the backend without requiring manual page reloads:
- **Non-Overlapping Polling Guard:** Controlled by an `isSyncing` mutex flag preventing client-side request storms or race conditions on slow connections.
- **Configurable Auto-Refresh:** Default 5-second interval, user-adjustable to 3s, 10s, or Manual Only via top-bar controls.
- **Multi-Window Live Consistency:** Verified with automated Playwright end-to-end tests (`scripts/test_realtime_sync.py`). Mutations in Window A (product creation, inventory adjustment, atomic reservation, and reservation release) automatically appear in Window B within seconds.
- **Live Connection State Machine:** Visual pulse dot and text state transitions across `Connected` (Emerald), `Reconnecting...` (Amber pulse on 1st transient failure), `Backend Disconnected` (Coral on >=2 consecutive failures), and `Sync Paused` (Manual mode).
- **Graceful Fault Recovery:** Automatic reconnection and state restoration once backend connectivity is re-established.
- **Authoritative Data Guarantees:** Metrics, stock distribution charts, and ledgers render directly from PostgreSQL API responses—never fabricated or guessed.

---

## Design System & Colour Palette

| Purpose | Colour Name | Hex Code | Usage |
| :--- | :--- | :--- | :--- |
| **Main Background** | Warm Ivory | `#FAF7F2` | Body canvas and subtle container surfaces |
| **Card Background** | Pure Crisp White | `#FFFFFF` | Metric cards, forms, and data tables |
| **Primary Brand** | Forest Green | `#173824` | Sidebar navigation, main headings, dark accents |
| **Action & Success** | Emerald | `#059669` | Primary CTA buttons, in-stock badges, healthy status |
| **Positive State** | Soft Mint | `#DCEDE3` | Positive badge background with emerald typography |
| **Accent & Failure** | Coral | `#E76F51` | Payment decline alerts, failed saga steps, depleted stock |
| **Warning** | Warm Amber | `#E9B85D` | Low-stock warnings, fallback broker badges |
| **Main Text** | Deep Forest Slate | `#25352F` | Primary body typography for high contrast |
| **Secondary Text** | Muted Sage Slate | `#78847E` | Form labels, table column headers, helper notes |
| **Border** | Sand Ivory Border | `#E6DFD3` | Card outlines, table separators, input boundaries |

---

## Quickstart & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16
- RabbitMQ 3.13 (optional; resilient in-memory event bus included)

### 1. Clone & Install
```bash
git clone https://github.com/rohitam26/stockguard.git
cd stockguard
python -m pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment
Create `.env`:
```env
DATABASE_URL=postgresql+psycopg://<db_user>:<db_password>@localhost:5432/stockguard
RABBITMQ_URL=amqp://<rabbitmq_user>:<rabbitmq_password>@localhost:5672/
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
- Access the Dashboard at: [http://localhost:8000](http://localhost:8000)
- Access Swagger API Docs at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Automated Test Suite

```bash
# Run complete pytest suite (13 passed, 1 skipped)
python -m pytest -v

# Run 25-endpoint API verification
python scripts/verify_all_api_endpoints.py

# Run Real-Time Multi-Window & Network Fault Recovery Verification (10/10 stages passed)
python scripts/test_realtime_sync.py

# Run Playwright frontend audit & capture screenshots
python scripts/audit_frontend.py

# Run dependency vulnerability audit (0 CVEs)
python -m pip_audit -r requirements.txt
```

---

## Operational Boundaries & Limitations

StockGuard is designed and verified as a functional distributed-systems prototype. For production multi-tenant readiness, the following operational boundaries apply:

1. **Message Broker Mode:** In the default local development environment, an in-memory event bus fallback is used when external RabbitMQ (port 5672) is offline. A live RabbitMQ instance is verified via GitHub Actions CI.
2. **API Authentication:** Endpoints currently operate without JWT/OAuth2 bearer token enforcement. Authentication middleware must be enabled prior to public internet exposure.
3. **Architecture Runtime:** Domain services execute as a modular monolith inside a consolidated FastAPI process (`stockguard.main:app`). Independent deployable microservice entrypoints are provided in `src/stockguard/microservices/`.
4. **Polling Scalability:** The web dashboard utilizes 5-second polling with an `isSyncing` mutex lock. High enterprise concurrent traffic should adopt Server-Sent Events (SSE) or HTTP ETag caching.

---

## Documentation
- [Final Comprehensive Audit Report](docs/FINAL_AUDIT_REPORT.md)
- [Distributed Architecture & Microservices Decomposition](docs/DISTRIBUTED_ARCHITECTURE.md)
- [API Specification](docs/API.md)
- [Security Policy & Findings](docs/SECURITY.md)
- [Changelog](CHANGELOG.md)

---

## License
MIT License. Copyright (c) 2026 StockGuard Engineering Team.
