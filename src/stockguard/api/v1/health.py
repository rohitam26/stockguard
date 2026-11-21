from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from stockguard.database import get_db, get_active_db_url, is_postgresql
from stockguard.messaging.rabbitmq import rabbitmq_client
from stockguard.models.outbox import OutboxMessage, OutboxStatus
from stockguard.observability.metrics import metrics
from stockguard.config import get_settings

router = APIRouter(prefix="/health", tags=["Health & Observability"])
settings = get_settings()


@router.get("")
def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check for API, database, and messaging broker."""
    db_status = "unhealthy"
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "engine": "PostgreSQL" if is_postgresql() else "SQLite",
            "url_masked": get_active_db_url().split("@")[-1]
            if "@" in get_active_db_url()
            else get_active_db_url(),
        },
        "messaging": {
            "broker": "RabbitMQ"
            if rabbitmq_client.is_connected
            else "In-Memory Event Bus (Fallback)",
            "connected": rabbitmq_client.is_connected,
        },
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness_probe():
    """Kubernetes liveness probe: returns 200 OK if FastAPI process is responsive."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness_probe(db: Session = Depends(get_db)):
    """Kubernetes readiness probe: verifies database connectivity before routing traffic."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {e}",
        )


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """Exposes Prometheus text-formatted metrics."""
    try:
        backlog_count = (
            db.execute(
                select(func.count(OutboxMessage.id)).where(
                    OutboxMessage.status == OutboxStatus.PENDING
                )
            ).scalar()
            or 0
        )
    except Exception:
        backlog_count = 0

    output = metrics.generate_prometheus_output(outbox_backlog=backlog_count)
    return Response(content=output, media_type="text/plain; version=0.0.4; charset=utf-8")
