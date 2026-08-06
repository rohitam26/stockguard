import uuid
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.models.base import utc_now
from stockguard.models.order import Order
from stockguard.models.fulfillment import Fulfillment, FulfillmentStatus
from stockguard.schemas.fulfillment import FulfillmentProcessRequest
from stockguard.services.outbox_service import OutboxService
from stockguard.services.order_service import OrderNotFoundException

logger = logging.getLogger("stockguard.fulfillment_service")


class FulfillmentNotFoundException(Exception):
    pass


class FulfillmentService:
    @staticmethod
    def initiate_fulfillment(db: Session, order_id: str, req: FulfillmentProcessRequest | None = None) -> Fulfillment:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            raise OrderNotFoundException(f"Order '{order_id}' not found.")

        existing = db.execute(select(Fulfillment).where(Fulfillment.order_id == order_id)).scalar_one_or_none()
        if existing:
            return existing

        carrier = req.carrier if req and req.carrier else "FAST_SHIP"
        tracking = req.tracking_number if req and req.tracking_number else f"TRK-{uuid.uuid4().hex[:10].upper()}"
        notes = req.notes if req else None

        fulfillment = Fulfillment(
            order_id=order_id,
            status=FulfillmentStatus.PACKING,
            tracking_number=tracking,
            carrier=carrier,
            notes=notes
        )
        db.add(fulfillment)
        db.flush()  # Crucial: populate fulfillment.id

        OutboxService.create_message(
            db=db,
            event_type="fulfillment.started",
            aggregate_type="fulfillment",
            aggregate_id=fulfillment.id,
            payload={
                "fulfillment_id": fulfillment.id,
                "order_id": order_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "status": fulfillment.status.value
            }
        )

        db.commit()
        db.refresh(fulfillment)
        logger.info("Initiated fulfillment for order %s (tracking: %s)", order_id, tracking)
        return fulfillment

    @staticmethod
    def update_status(db: Session, order_id: str, status: FulfillmentStatus) -> Fulfillment:
        fulfillment = db.execute(select(Fulfillment).where(Fulfillment.order_id == order_id)).scalar_one_or_none()
        if not fulfillment:
            raise FulfillmentNotFoundException(f"Fulfillment for order '{order_id}' not found.")

        fulfillment.status = status
        now = utc_now()
        if status == FulfillmentStatus.SHIPPED:
            fulfillment.shipped_at = now
        elif status == FulfillmentStatus.DELIVERED:
            fulfillment.delivered_at = now

        OutboxService.create_message(
            db=db,
            event_type="fulfillment.status_updated",
            aggregate_type="fulfillment",
            aggregate_id=fulfillment.id,
            payload={
                "fulfillment_id": fulfillment.id,
                "order_id": order_id,
                "status": status.value,
                "updated_at": now.isoformat()
            }
        )

        db.commit()
        db.refresh(fulfillment)
        return fulfillment

    @staticmethod
    def get_fulfillment_by_order(db: Session, order_id: str) -> Fulfillment | None:
        return db.execute(select(Fulfillment).where(Fulfillment.order_id == order_id)).scalar_one_or_none()
