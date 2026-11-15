# Changelog

All notable changes to the StockGuard project are documented in this file.

## [1.0.0] - 2026-11-15

### Added
- **Core Domain & Models:** Product, InventoryItem, Reservation, Order, OrderItem, Payment, Fulfillment, OutboxMessage, and ProcessedEvent models in SQLAlchemy 2.0.
- **Database Constraints & Schema:** PostgreSQL 16 schema with strict CHECK constraints (`available_stock >= 0`, `reserved_stock >= 0`, `allocated_stock >= 0`), unique indexes, and foreign keys with CASCADE delete.
- **Atomic Reservation Engine:** High-concurrency atomic inventory reservation using conditional SQL UPDATE statements and row locking, preventing overselling under heavy load.
- **Client Idempotency:** Endpoints support client-supplied idempotency keys (`reservations`, `orders`) preventing duplicate deductions.
- **Distributed Saga Orchestrator:** Full checkout coordination across Inventory, Payment, and Fulfillment with backward compensating transactions on payment decline or partial stock depletion.
- **Transactional Outbox Pattern:** Outbox table staging domain events in the same DB transaction, published to RabbitMQ / in-memory event bus with retry logic and Dead Letter Queue routing.
- **Consumer Idempotency:** Deduplication via `processed_events` table guaranteeing exactly-once side-effects.
- **Interactive Web Dashboard:** Modern, responsive Single Page Application with live stock monitors, low-stock alerts, active reservation countdowns, interactive checkout, and visual Saga stepper.
- **Automated Test Suite:** Comprehensive pytest suite covering unit tests, API integration tests, Saga compensation, failure recovery, idempotency, and the 100-request PostgreSQL concurrency experiment.
- **Real Performance Benchmarks:** Reproducible benchmark script measuring latency percentiles (avg, p50, p95, p99) and request throughput on live PostgreSQL.
- **Genuine Screenshots:** Headless browser captures of Dashboard Overview, Saga Visualizer, Atomic Reservations, Transactional Outbox, and Swagger UI docs.
- **Docker & CI:** Dockerfile, docker-compose.yml (PostgreSQL 16, RabbitMQ 3.13, API), and GitHub Actions CI workflow.
