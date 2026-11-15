import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.config import get_settings
from stockguard.models.outbox import OutboxMessage, OutboxStatus
from stockguard.messaging.rabbitmq import rabbitmq_client

logger = logging.getLogger("stockguard.messaging.outbox_worker")
settings = get_settings()


class OutboxWorker:
    @staticmethod
    def process_pending_messages(db: Session, batch_size: int = 50) -> int:
        """
        Polls pending outbox messages and reliably dispatches them to the message broker.
        Guarantees At-Least-Once Delivery via Transactional Outbox.
        """
        messages = list(db.execute(
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.PENDING)
            .order_by(OutboxMessage.created_at.asc())
            .limit(batch_size)
        ).scalars().all())

        if not messages:
            return 0

        published_count = 0
        now = datetime.now(timezone.utc)

        for msg in messages:
            try:
                payload = json.loads(msg.payload) if msg.payload else {}
                headers = json.loads(msg.headers) if msg.headers else {}
            except Exception as parse_err:
                msg.status = OutboxStatus.FAILED
                msg.last_error = f"Payload JSON parse error: {parse_err}"
                continue

            success = rabbitmq_client.publish(
                routing_key=msg.event_type,
                payload=payload,
                message_id=msg.id,
                headers=headers
            )

            if success:
                msg.status = OutboxStatus.PUBLISHED
                msg.processed_at = now
                published_count += 1
            else:
                msg.retry_count += 1
                msg.last_error = "Broker publish failed"
                if msg.retry_count >= settings.RABBITMQ_RETRY_LIMIT:
                    msg.status = OutboxStatus.FAILED
                    logger.error("Outbox message %s failed after %d retries.", msg.id, msg.retry_count)

        db.commit()
        if published_count > 0:
            logger.info("Outbox worker processed %d messages", published_count)
        return published_count
