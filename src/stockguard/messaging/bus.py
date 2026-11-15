import json
import logging
from typing import Callable, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.models.event import ProcessedEvent

logger = logging.getLogger("stockguard.messaging.bus")


class EventBus:
    """
    Unified Event Bus abstraction supporting broker decoupling.
    Provides consumer idempotency tracking and dead-letter routing.
    """
    def __init__(self):
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._dead_letter_queue: list[dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("Subscribed handler %s to event '%s'", handler.__name__, event_type)

    def is_event_processed(self, db: Session, message_id: str, consumer_name: str) -> bool:
        """
        Consumer Idempotency check. Returns True if event was already handled by consumer.
        """
        record_id = f"{consumer_name}:{message_id}"
        existing = db.execute(
            select(ProcessedEvent).where(ProcessedEvent.id == record_id)
        ).scalar_one_or_none()
        return existing is not None

    def mark_event_processed(
        self,
        db: Session,
        message_id: str,
        consumer_name: str,
        event_type: str
    ):
        """
        Record processed event to guarantee idempotent consumer execution.
        """
        record_id = f"{consumer_name}:{message_id}"
        processed = ProcessedEvent(
            id=record_id,
            consumer_name=consumer_name,
            event_type=event_type,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(processed)
        db.commit()

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        message_id: str,
        headers: dict[str, Any] | None = None,
        max_retries: int = 3
    ) -> bool:
        """
        Publishes event to registered local subscribers with retry and DLQ routing.
        """
        logger.debug("Publishing event %s (id: %s)", event_type, message_id)
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug("No local handlers for event %s", event_type)
            return True

        message_envelope = {
            "id": message_id,
            "event_type": event_type,
            "payload": payload,
            "headers": headers or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        all_ok = True
        for handler in handlers:
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    handler(message_envelope)
                    success = True
                    break
                except Exception as e:
                    logger.warning(
                        "Handler %s failed on event %s (attempt %d/%d): %s",
                        handler.__name__, event_type, attempt, max_retries, e
                    )
            if not success:
                logger.error("Handler %s exhausted retries. Routing to DLQ.", handler.__name__)
                self._dead_letter_queue.append({
                    "envelope": message_envelope,
                    "handler": handler.__name__,
                    "failed_at": datetime.now(timezone.utc).isoformat()
                })
                all_ok = False

        return all_ok

    @property
    def dlq_messages(self) -> list[dict[str, Any]]:
        return list(self._dead_letter_queue)


# Global singleton event bus
event_bus = EventBus()
