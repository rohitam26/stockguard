from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.models.outbox import OutboxMessage
from stockguard.messaging.outbox_worker import OutboxWorker

router = APIRouter(prefix="/outbox", tags=["Transactional Outbox"])


@router.get("")
def list_outbox_messages(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = (
        select(OutboxMessage).offset(skip).limit(limit).order_by(OutboxMessage.created_at.desc())
    )
    messages = list(db.execute(query).scalars().all())
    return [
        {
            "id": m.id,
            "event_type": m.event_type,
            "aggregate_type": m.aggregate_type,
            "aggregate_id": m.aggregate_id,
            "status": m.status.value,
            "retry_count": m.retry_count,
            "last_error": m.last_error,
            "created_at": m.created_at.isoformat(),
            "processed_at": m.processed_at.isoformat() if m.processed_at else None,
        }
        for m in messages
    ]


@router.post("/process")
def process_outbox_messages(batch_size: int = 50, db: Session = Depends(get_db)):
    count = OutboxWorker.process_pending_messages(db, batch_size=batch_size)
    return {"status": "ok", "processed_count": count}
