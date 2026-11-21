import logging
from stockguard.config import get_settings

logger = logging.getLogger("stockguard.observability.tracing")
settings = get_settings()


def setup_tracing(app=None):
    """
    Initializes OpenTelemetry distributed tracing if enabled in settings.
    Gracefully no-ops if OpenTelemetry is disabled.
    """
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is disabled (OTEL_ENABLED=False).")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        if app:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            logger.info(
                "OpenTelemetry FastAPI instrumentation initialized for service %s",
                settings.OTEL_SERVICE_NAME,
            )

        return trace.get_tracer(settings.OTEL_SERVICE_NAME)
    except Exception as e:
        logger.warning("Could not initialize OpenTelemetry tracing: %s", e)
        return None
