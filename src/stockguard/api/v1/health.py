from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from stockguard.database import get_db, get_active_db_url, is_postgresql
from stockguard.messaging.rabbitmq import rabbitmq_client
from stockguard.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("")
def health_check(db: Session = Depends(get_db)):
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
            "url_masked": get_active_db_url().split("@")[-1] if "@" in get_active_db_url() else get_active_db_url()
        },
        "messaging": {
            "broker": "RabbitMQ" if rabbitmq_client.is_connected else "In-Memory Event Bus (Fallback)",
            "connected": rabbitmq_client.is_connected
        },
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }
