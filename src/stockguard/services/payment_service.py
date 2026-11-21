import uuid
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.models.order import Order
from stockguard.models.payment import Payment, PaymentStatus
from stockguard.schemas.payment import PaymentProcessRequest
from stockguard.services.outbox_service import OutboxService
from stockguard.services.order_service import OrderNotFoundException

logger = logging.getLogger("stockguard.payment_service")


class PaymentService:
    @staticmethod
    def process_payment(db: Session, req: PaymentProcessRequest) -> Payment:
        order = db.execute(select(Order).where(Order.id == req.order_id)).scalar_one_or_none()
        if not order:
            raise OrderNotFoundException(f"Order '{req.order_id}' not found.")

        # Check if existing payment exists
        existing_payment = db.execute(
            select(Payment).where(Payment.order_id == req.order_id)
        ).scalar_one_or_none()
        if existing_payment:
            logger.info(
                "Payment already exists for order %s (status: %s)",
                req.order_id,
                existing_payment.status,
            )
            return existing_payment

        # Simulation logic:
        is_failure = req.simulate_failure or req.payment_method == "CARD_DECLINED"

        status = PaymentStatus.FAILED if is_failure else PaymentStatus.SUCCESS
        txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}" if not is_failure else None
        failure_msg = (
            req.failure_reason or "Simulated payment decline / insufficient funds"
            if is_failure
            else None
        )

        payment = Payment(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency,
            status=status,
            transaction_id=txn_id,
            payment_method=req.payment_method,
            failure_reason=failure_msg,
        )
        db.add(payment)
        db.flush()  # Crucial: populate payment.id before outbox record!

        OutboxService.create_message(
            db=db,
            event_type="payment.processed",
            aggregate_type="payment",
            aggregate_id=payment.id,
            payload={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": payment.status.value,
                "transaction_id": payment.transaction_id,
                "failure_reason": payment.failure_reason,
            },
        )

        db.commit()
        db.refresh(payment)
        logger.info(
            "Payment %s processed for order %s with status %s", payment.id, order.id, payment.status
        )
        return payment

    @staticmethod
    def get_payment_by_order(db: Session, order_id: str) -> Payment | None:
        return db.execute(select(Payment).where(Payment.order_id == order_id)).scalar_one_or_none()
