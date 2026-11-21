import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from stockguard.observability.metrics import metrics

logger = logging.getLogger("stockguard.observability")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Assigns or propagates X-Correlation-ID header across requests.
    2. Measures request execution latency.
    3. Records Prometheus metrics.
    4. Attaches correlation headers to response for client tracing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

            # Record metrics
            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration,
            )
            return response
        except Exception as exc:
            duration = time.perf_counter() - start_time
            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_seconds=duration,
            )
            logger.error(
                "[%s] Unhandled exception in %s %s: %s",
                correlation_id,
                request.method,
                request.url.path,
                exc,
            )
            raise exc
