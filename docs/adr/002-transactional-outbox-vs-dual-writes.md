# ADR 002: Transactional Outbox Pattern vs Dual Writes

## Status
Accepted

## Context
Directly writing to PostgreSQL and publishing messages to RabbitMQ in separate operations creates dual-write vulnerabilities: if the application crashes or the broker connection drops between the database commit and the broker publish, messages are silently lost.

## Decision
Implement the **Transactional Outbox Pattern**:
1. Domain state mutations and outbox message records are written within the same atomic PostgreSQL transaction.
2. An asynchronous background worker (`OutboxWorker`) polls `outbox_messages` using `SELECT ... FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ with publisher confirms.
3. Upon confirmed delivery, messages are marked `PUBLISHED`.

## Consequences
- **Positive:** Eliminates dual-write inconsistencies; guarantees at-least-once message delivery.
- **Negative:** Minor asynchronous publication latency (configurable polling interval).
