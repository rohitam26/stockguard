# ADR 003: Pessimistic Row Locking & Database Constraints vs Distributed Locks

## Status
Accepted

## Context
Preventing overselling under high concurrency requires serializing stock decrements. Alternatives include distributed Redis locks (Redlock) or database-level concurrency control.

## Decision
Enforce concurrency control directly at the database layer via PostgreSQL:
1. `CHECK (available_stock >= 0)` constraint enforced by the relational engine.
2. Atomic conditional updates: `UPDATE inventory_items SET available_stock = available_stock - :qty WHERE sku = :sku AND available_stock >= :qty`.
3. Explicit row locking (`SELECT ... FOR UPDATE`) during critical reservation workflows.

## Consequences
- **Positive:** Relies on PostgreSQL's battle-tested ACID engine as the single source of truth; avoids split-brain and lock lease expiration failures inherent to distributed Redis locks.
- **Negative:** Increased lock wait times on single contested SKUs during extreme concurrency bursts.
