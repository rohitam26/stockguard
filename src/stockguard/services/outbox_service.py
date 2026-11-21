import json
from typing import Any
from sqlalchemy.orm import Session
from stockguard.models.outbox import OutboxMessage, OutboxStatus


class OutboxService:
    @staticmethod
    def create_message(
        db: Session,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        headers: dict[str, Any] | None = None,
    ) -> OutboxMessage:
        """
        Creates an OutboxMessage within the caller's active database transaction.
        Guarantees transactional consistency between domain state and published events.
        """
        message = OutboxMessage(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=json.dumps(payload, default=str),
            headers=json.dumps(headers or {}, default=str),
            status=OutboxStatus.PENDING,
        )
        db.add(message)
        return message
