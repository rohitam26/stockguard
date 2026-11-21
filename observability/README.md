# StockGuard Observability & Production Monitoring Architecture

StockGuard incorporates production-grade observability across distributed tracing, structured logging, real-time metrics, and health inspection.

## 1. Components

### A. Distributed Tracing (OpenTelemetry)
- **Automatic Context Propagation:** Incoming requests carry or are assigned a unique correlation ID via `X-Correlation-ID` or `X-Request-ID`.
- **OpenTelemetry Instrumentation:** Optional distributed tracing via `opentelemetry-instrumentation-fastapi` enabled when `OTEL_ENABLED=true`.

### B. Structured Logging
- **JSON Formatter:** `stockguard.observability.logging.JSONFormatter` outputs structured JSON logs with timestamp, log level, correlation ID, trace ID, module, and line number.
- **Redaction of Sensitive Data:** Authorization headers, tokens, and plaintext passwords are never emitted to log streams.

### C. Prometheus Metrics Exposition
- Available at both `/metrics` (top-level) and `/api/v1/health/metrics`.
- **Key Metrics:**
  - `stockguard_http_requests_total`: Total HTTP requests partitioned by HTTP method, route, and status code.
  - `stockguard_http_request_duration_seconds`: Latency summaries with P50 and P95 quantile percentiles.
  - `stockguard_reservations_total`: Counter tracking reservation attempts by outcome (`success`, `insufficient_stock`, `conflict`).
  - `stockguard_outbox_backlog_total`: Real-time gauge measuring pending messages in `outbox_messages`.

### D. Kubernetes Health Probes
- **`/api/v1/health/live`**: Process liveness probe (returns 200 OK if FastAPI event loop is responsive).
- **`/api/v1/health/ready`**: Readiness probe verifying PostgreSQL connectivity before accepting ingress traffic.
- **`/api/v1/health`**: Comprehensive health endpoint inspecting database, messaging broker, and operational mode.

## 2. Setting Up Prometheus & Grafana Locally

```bash
# Start Prometheus with StockGuard scrape config
prometheus --config.file=observability/prometheus.yml

# Import Grafana dashboard
# Navigate to Grafana (http://localhost:3000) -> Dashboards -> Import -> Upload observability/dashboards/stockguard_dashboard.json
```
