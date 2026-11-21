# ADR 001: Modular Monolith with Decoupled Entrypoints

## Status
Accepted

## Context
StockGuard coordinates high-concurrency inventory allocations, payment processing, and fulfillment. We evaluated whether to architect the system as a distributed microservice cluster or a consolidated modular monolith.

## Decision
We chose a **Modular Monolith** architecture with decoupled microservice entrypoints (`src/stockguard/microservices/`):
- All services maintain strict internal boundary separation and Pydantic data schemas.
- In-process execution eliminates network serialization latency during high-contention flash sales.
- Enables single database transaction boundaries between domain operations and Transactional Outbox staging.

## Consequences
- **Positive:** Low operational overhead, zero inter-service network flakiness during checkout, atomic transactional outbox commits.
- **Negative:** Services scale together in the monolith configuration. Decoupled microservice entrypoints are provided when independent horizontal scaling is required.
