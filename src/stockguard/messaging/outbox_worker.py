import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.config import get_settings
from stockguard.models.outbox import OutboxMessage, OutboxStatus
from stockguard.messaging.rabbitmq import rabbitmq_client

logger = logging.getLogger("stockguard.messaging.outbox_worker")
settings = get_settings()


class OutboxWorker:
    @staticmethod
    def recover_stuck_messages(db: Session, stuck_timeout_seconds: int = 60) -> int:
        """
        Recovers messages stuck in PROCESSING state due to worker crashes.
        Resets them to PENDING so another worker can safely pick them up.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=stuck_timeout_seconds)

        stuck_messages = list(
            db.execute(
                select(OutboxMessage).where(
                    OutboxMessage.status == OutboxStatus.PROCESSING,
                    OutboxMessage.updated_at < cutoff,
                )
            )
            .scalars()
            .all()
        )

        if not stuck_messages:
            return 0

        recovered_count = 0
        for msg in stuck_messages:
            msg.retry_count += 1
            if msg.retry_count >= settings.RABBITMQ_RETRY_LIMIT:
                msg.status = OutboxStatus.FAILED
                msg.last_error = f"Quarantined: Message exceeded {settings.RABBITMQ_RETRY_LIMIT} retries after worker crash"
                logger.error(
                    "Outbox message %s quarantined as FAILED after crash recovery retries", msg.id
                )
            else:
                msg.status = OutboxStatus.PENDING
                msg.last_error = f"Recovered from dead worker crash at {now.isoformat()}"
                recovered_count += 1
                logger.warning(
                    "Recovered stuck outbox message %s back to PENDING (retry: %d)",
                    msg.id,
                    msg.retry_count,
                )

        db.commit()
        return recovered_count

    @staticmethod
    def process_pending_messages(db: Session, batch_size: int = 50) -> int:
        """
        Polls pending outbox messages and reliably dispatches them to the message broker.
        Guarantees At-Least-Once Delivery via Transactional Outbox.
        Uses FOR UPDATE SKIP LOCKED on PostgreSQL to prevent concurrent worker contention.
        """
        # First recover any stuck messages
        OutboxWorker.recover_stuck_messages(db)

        # Build query for pending messages
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.PENDING)
            .order_by(OutboxMessage.created_at.asc())
            .limit(batch_size)
        )

        # Use FOR UPDATE SKIP LOCKED if running on PostgreSQL to prevent duplicate processing by concurrent workers
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        messages = list(db.execute(stmt).scalars().all())

        if not messages:
            return 0

        # Mark messages as PROCESSING immediately within this transaction
        for msg in messages:
            msg.status = OutboxStatus.PROCESSING
        db.flush()

        published_count = 0
        now = datetime.now(timezone.utc)

        for msg in messages:
            try:
                payload = json.loads(msg.payload) if msg.payload else {}
                headers = json.loads(msg.headers) if msg.headers else {}
            except Exception as parse_err:
                # Quarantined poison pill: invalid JSON will never succeed, isolate as FAILED immediately
                msg.status = OutboxStatus.FAILED
                msg.last_error = f"Poison pill quarantined: JSON parse error ({parse_err})"
                logger.error("Quarantining poison outbox message %s: %s", msg.id, parse_err)
                continue

            success = rabbitmq_client.publish(
                routing_key=msg.event_type, payload=payload, message_id=msg.id, headers=headers
            )

            if success:
                msg.status = OutboxStatus.PUBLISHED
                msg.processed_at = now
                published_count += 1
            else:
                msg.retry_count += 1
                msg.last_error = f"Broker publish failed (attempt {msg.retry_count})"
                if msg.retry_count >= settings.RABBITMQ_RETRY_LIMIT:
                    msg.status = OutboxStatus.FAILED
                    logger.error(
                        "Outbox message %s permanently failed after %d retries.",
                        msg.id,
                        msg.retry_count,
                    )
                else:
                    # Reset back to PENDING for subsequent backoff retry
                    msg.status = OutboxStatus.PENDING

        db.commit()
        if published_count > 0:
            logger.info("Outbox worker published %d messages to broker", published_count)
        return published_count
