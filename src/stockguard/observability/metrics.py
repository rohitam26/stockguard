import threading
from collections import defaultdict


class PrometheusMetrics:
    """
    Lightweight, dependency-free Prometheus exposition metrics registry.
    Collects counters, gauges, and request latency summaries.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.request_counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self.request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
        self.reservation_counts: dict[str, int] = defaultdict(int)

    def record_request(self, method: str, path: str, status_code: int, duration_seconds: float):
        # Normalize paths to prevent cardinality explosion
        clean_path = path
        if path.startswith("/api/v1/inventory/") and len(path.split("/")) > 4:
            clean_path = "/api/v1/inventory/{sku}"
        elif path.startswith("/api/v1/reservations/") and len(path.split("/")) > 4:
            clean_path = "/api/v1/reservations/{id}"
        elif path.startswith("/api/v1/orders/") and len(path.split("/")) > 4:
            clean_path = "/api/v1/orders/{id}"

        with self._lock:
            self.request_counts[(method, clean_path, status_code)] += 1
            durations = self.request_durations[(method, clean_path)]
            durations.append(duration_seconds)
            if len(durations) > 200:
                self.request_durations[(method, clean_path)] = durations[-200:]

    def record_reservation(self, outcome: str):
        with self._lock:
            self.reservation_counts[outcome] += 1

    def generate_prometheus_output(self, outbox_backlog: int = 0) -> str:
        lines = [
            "# HELP stockguard_http_requests_total Total HTTP requests handled",
            "# TYPE stockguard_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), count in self.request_counts.items():
                lines.append(
                    f'stockguard_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.append(
                "# HELP stockguard_http_request_duration_seconds HTTP request latency summary"
            )
            lines.append("# TYPE stockguard_http_request_duration_seconds summary")
            for (method, path), durations in self.request_durations.items():
                if durations:
                    count = len(durations)
                    total = sum(durations)
                    durations_sorted = sorted(durations)
                    p50 = durations_sorted[int(count * 0.50)]
                    p95 = durations_sorted[min(count - 1, int(count * 0.95))]
                    lines.append(
                        f'stockguard_http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.5"}} {p50:.4f}'
                    )
                    lines.append(
                        f'stockguard_http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.95"}} {p95:.4f}'
                    )
                    lines.append(
                        f'stockguard_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.4f}'
                    )
                    lines.append(
                        f'stockguard_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}'
                    )

            lines.append(
                "# HELP stockguard_reservations_total Total reservation operations by outcome"
            )
            lines.append("# TYPE stockguard_reservations_total counter")
            for outcome, count in self.reservation_counts.items():
                lines.append(f'stockguard_reservations_total{{outcome="{outcome}"}} {count}')

        lines.append(
            "# HELP stockguard_outbox_backlog_total Current pending transactional outbox events"
        )
        lines.append("# TYPE stockguard_outbox_backlog_total gauge")
        lines.append(f"stockguard_outbox_backlog_total {outbox_backlog}")

        return "\n".join(lines) + "\n"


metrics = PrometheusMetrics()
