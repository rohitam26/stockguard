# StockGuard Observability & Telemetry Specification

This document details the metrics, distributed tracing, structured logging, and health probe architecture within StockGuard.

---

## 1. Distributed Tracing & Correlation IDs

Every inbound HTTP request is processed through `ObservabilityMiddleware`:
1. Inspects request headers for `X-Correlation-ID` or `X-Request-ID`.
2. Generates a cryptographically random UUID4 correlation ID if missing.
3. Sets `X-Correlation-ID` and `X-Response-Time` in response headers.
4. If `OTEL_ENABLED=true`, exports OpenTelemetry distributed trace spans with service name `stockguard`.

---

## 2. Prometheus Exposition Metrics (`/metrics`)

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `stockguard_http_requests_total` | Counter | `method`, `path`, `status` | Cumulative HTTP requests processed |
| `stockguard_http_request_duration_seconds` | Summary | `method`, `path`, `quantile` | Request latency percentiles (P50, P95) |
| `stockguard_reservations_total` | Counter | `outcome` | Reservation operations by outcome (`success`, `insufficient_stock`) |
| `stockguard_outbox_backlog_total` | Gauge | None | Number of pending messages in `outbox_messages` |

---

## 3. Structured JSON Logging

Logs are formatted in structured JSON for ELK / Grafana Loki / CloudWatch ingestion:
```json
{
  "timestamp": "2026-11-22T03:30:00.000000Z",
  "level": "INFO",
  "logger": "stockguard.services.reservation_service",
  "message": "Atomically reserved 2 units of SKU LAPTOP-PRO-16",
  "module": "reservation_service",
  "line": 84,
  "correlation_id": "c7a8b9d0-1234-5678-9abc-def012345678"
}
```

---

## 4. Kubernetes Health Probes

- **Liveness (`/api/v1/health/live`):** Returns 200 OK if the FastAPI process is alive and responsive.
- **Readiness (`/api/v1/health/ready`):** Executes `SELECT 1` against PostgreSQL; returns 200 OK if ready to accept traffic, or 503 Service Unavailable if database is unreachable.
