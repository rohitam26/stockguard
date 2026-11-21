# StockGuard Failure Modes & Disaster Recovery Runbook

This document describes realistic failure scenarios, automatic system behaviors, manual remediation steps, and verification commands.

---

## 1. Failure Scenarios & Recovery Matrix

| Failure Mode | Trigger / Cause | System Behavior | Recovery Mechanism | Verification Test |
| :--- | :--- | :--- | :--- | :--- |
| **Worker Crash During Outbox Dispatch** | OOM kill, unhandled signal, hardware failure | Message left in `PROCESSING` state in database | `OutboxWorker.recover_stuck_messages()` resets messages older than 60s to `PENDING` | `test_outbox_worker_crash_recovery_of_stuck_messages` |
| **Poison / Corrupt Outbox Payload** | Malformed JSON, corrupted data serialization | Worker catches `JSONDecodeError` | Message marked `FAILED` with quarantined error trace; worker continues | `test_poison_message_quarantine` |
| **Duplicate AMQP Message Delivery** | Network partition before consumer `basic_ack` | Duplicate delivery with identical `message_id` | Consumer queries `processed_events` table; identifies duplicate, skips execution, issues `basic_ack` | `test_consumer_message_deduplication` |
| **Payment Gateway Decline** | Card declined, insufficient funds, timeout | Saga Step 2 fails | Saga initiates backward compensation: releases all acquired stock reservations; marks order `CANCELLED` | `test_saga_compensation_on_payment_decline` |
| **Message Broker Partition / Offline** | RabbitMQ broker restart, network partition | Socket connection fails | System falls back seamlessly to thread-safe in-memory event bus | `test_rabbitmq_real.py` (clean skip/fallback) |
| **Database Disconnection During Reservation** | PostgreSQL service restart | Connection timeout | Client receives HTTP 503/500; transaction rolls back cleanly; no orphan stock decrement | `test_concurrency_postgres.py` |

---

## 2. Operator Remediation Commands

### Check Liveness and Readiness
```bash
# Check if API event loop is responsive
curl -f http://localhost:8000/api/v1/health/live

# Check if PostgreSQL database is connected and ready
curl -f http://localhost:8000/api/v1/health/ready

# Comprehensive topology inspection
curl http://localhost:8000/api/v1/health
```

### Inspect Outbox Backlog & Quarantine
```sql
-- Count pending, processing, and failed outbox records
SELECT status, count(*) FROM outbox_messages GROUP BY status;

-- Inspect quarantined poison messages
SELECT id, event_type, last_error, updated_at FROM outbox_messages WHERE status = 'FAILED' LIMIT 10;
```

### Trigger Stale Reservation Sweep Manually
```bash
curl -X POST http://localhost:8000/api/v1/reservations/expire-stale
```
