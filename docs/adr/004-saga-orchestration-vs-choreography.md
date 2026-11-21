# ADR 004: Orchestrator-Driven Saga vs Event Choreography

## Status
Accepted

## Context
Multi-step checkout involves inventory reservation, payment processing, and fulfillment dispatch. If payment fails, acquired stock holds must be reliably compensated.

## Decision
Use an **Orchestrator-driven Saga** (`SagaOrchestrator`):
- A centralized coordinator manages execution order, evaluates stage outcomes, and coordinates backward compensating actions on failure.
- In the event of a payment decline, the orchestrator explicitly invokes `release_reservation()` across all acquired items, updates order status to `CANCELLED`, and stages outbox compensation events.

## Consequences
- **Positive:** Clear centralized failure visibility, simplified debugging, and guaranteed compensation flow without complex distributed event loop choreography.
- **Negative:** Coordinator serves as a logical orchestrator, requiring robust exception handling.
