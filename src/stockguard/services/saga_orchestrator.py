import logging
from typing import Any
from sqlalchemy.orm import Session
from stockguard.models.order import OrderStatus
from stockguard.models.payment import PaymentStatus
from stockguard.schemas.reservation import ReservationCreateRequest
from stockguard.schemas.payment import PaymentProcessRequest
from stockguard.services.order_service import OrderService
from stockguard.services.reservation_service import ReservationService
from stockguard.services.payment_service import PaymentService
from stockguard.services.fulfillment_service import FulfillmentService
from stockguard.services.inventory_service import InsufficientStockException

logger = logging.getLogger("stockguard.saga_orchestrator")


class SagaExecutionResult:
    def __init__(
        self,
        order_id: str,
        success: bool,
        stage: str,
        message: str,
        reservations: list[str] | None = None,
        payment_status: str | None = None,
        fulfillment_status: str | None = None,
        compensated: bool = False,
    ):
        self.order_id = order_id
        self.success = success
        self.stage = stage
        self.message = message
        self.reservations = reservations or []
        self.payment_status = payment_status
        self.fulfillment_status = fulfillment_status
        self.compensated = compensated

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "stage": self.stage,
            "message": self.message,
            "reservations": self.reservations,
            "payment_status": self.payment_status,
            "fulfillment_status": self.fulfillment_status,
            "compensated": self.compensated,
        }


class SagaOrchestrator:
    @staticmethod
    def execute_order_checkout(
        db: Session,
        order_id: str,
        payment_method: str = "CREDIT_CARD",
        simulate_payment_failure: bool = False,
    ) -> SagaExecutionResult:
        """
        Executes the Order Checkout Distributed Saga with automated compensation.
        Steps:
        1. Reserve Inventory (Atomic, with rollback on insufficient stock)
        2. Process Payment (With full reservation release compensation on failure)
        3. Confirm Reservations & Initiate Fulfillment
        """
        order = OrderService.get_order(db, order_id)
        logger.info(
            "Starting Saga for order %s (amount: %s)", order.order_number, order.total_amount
        )

        # Idempotency: If order has already reached terminal completion or cancellation, return existing state
        if order.status == OrderStatus.COMPLETED:
            logger.info("Saga checkout idempotent hit: order %s already completed.", order_id)
            return SagaExecutionResult(
                order_id=order_id,
                success=True,
                stage="COMPLETED",
                message="Order already completed (idempotent duplicate request)",
                compensated=False,
            )
        if order.status in (OrderStatus.CANCELLED, OrderStatus.FAILED):
            logger.info(
                "Saga checkout idempotent hit: order %s already cancelled/failed.", order_id
            )
            return SagaExecutionResult(
                order_id=order_id,
                success=False,
                stage="FAILED",
                message=f"Order already in terminal state: {order.status.value}",
                compensated=True,
            )

        # -----------------------------------------------------------------
        # STEP 1: INVENTORY RESERVATION
        # -----------------------------------------------------------------
        OrderService.update_order_status(db, order_id, OrderStatus.RESERVING)
        acquired_reservation_ids: list[str] = []

        try:
            for item in order.items:
                res_key = f"saga-res-{order.id}-{item.sku}"
                req = ReservationCreateRequest(
                    sku=item.sku,
                    quantity=item.quantity,
                    order_id=order.id,
                    ttl_seconds=600,
                    idempotency_key=res_key,
                )
                res = ReservationService.create_reservation(db, req)
                acquired_reservation_ids.append(res.id)

        except InsufficientStockException as e:
            logger.warning(
                "Saga step 1 failed: Insufficient stock. Compensating acquired reservations. Error: %s",
                e,
            )
            # COMPENSATING ACTION: Release any reservations acquired in earlier iterations
            for r_id in acquired_reservation_ids:
                try:
                    ReservationService.release_reservation(
                        db, r_id, reason="Saga compensation: partial reservation failure"
                    )
                except Exception as comp_err:
                    logger.error("Error compensating reservation %s: %s", r_id, comp_err)

            OrderService.update_order_status(
                db, order_id, OrderStatus.FAILED, failure_reason=f"Insufficient inventory: {e}"
            )
            return SagaExecutionResult(
                order_id=order_id,
                success=False,
                stage="RESERVATION",
                message=str(e),
                reservations=acquired_reservation_ids,
                compensated=True,
            )

        except Exception as e:
            logger.error("Unexpected error in Saga reservation step: %s", e)
            for r_id in acquired_reservation_ids:
                ReservationService.release_reservation(
                    db, r_id, reason="Saga compensation: unexpected error"
                )
            OrderService.update_order_status(
                db, order_id, OrderStatus.FAILED, failure_reason=str(e)
            )
            return SagaExecutionResult(
                order_id=order_id,
                success=False,
                stage="RESERVATION",
                message=f"Reservation failed: {e}",
                compensated=True,
            )

        OrderService.update_order_status(db, order_id, OrderStatus.RESERVED)

        # -----------------------------------------------------------------
        # STEP 2: PAYMENT PROCESSING
        # -----------------------------------------------------------------
        OrderService.update_order_status(db, order_id, OrderStatus.PAYMENT_PENDING)
        payment_req = PaymentProcessRequest(
            order_id=order.id,
            payment_method=payment_method,
            simulate_failure=simulate_payment_failure,
        )
        payment = PaymentService.process_payment(db, payment_req)

        if payment.status != PaymentStatus.SUCCESS:
            logger.warning(
                "Saga step 2 failed: Payment unsuccessful (%s). Triggering SAGA COMPENSATION.",
                payment.failure_reason,
            )
            # COMPENSATING ACTION: Release ALL reservations acquired for this order
            for r_id in acquired_reservation_ids:
                try:
                    ReservationService.release_reservation(
                        db,
                        r_id,
                        reason=f"Saga compensation: payment failed ({payment.failure_reason})",
                    )
                except Exception as comp_err:
                    logger.error(
                        "Error during payment compensation for reservation %s: %s", r_id, comp_err
                    )

            OrderService.update_order_status(
                db,
                order_id,
                OrderStatus.CANCELLED,
                failure_reason=f"Payment declined: {payment.failure_reason}",
            )
            return SagaExecutionResult(
                order_id=order_id,
                success=False,
                stage="PAYMENT",
                message=f"Payment declined: {payment.failure_reason}",
                reservations=acquired_reservation_ids,
                payment_status=payment.status.value,
                compensated=True,
            )

        OrderService.update_order_status(db, order_id, OrderStatus.PAID)

        # -----------------------------------------------------------------
        # STEP 3: CONFIRM RESERVATIONS & FULFILLMENT
        # -----------------------------------------------------------------
        for r_id in acquired_reservation_ids:
            ReservationService.confirm_reservation(db, r_id)

        OrderService.update_order_status(db, order_id, OrderStatus.FULFILLING)
        fulfillment = FulfillmentService.initiate_fulfillment(db, order_id)
        OrderService.update_order_status(db, order_id, OrderStatus.COMPLETED)

        logger.info(
            "Saga completed successfully for order %s. Tracking: %s",
            order.order_number,
            fulfillment.tracking_number,
        )
        return SagaExecutionResult(
            order_id=order_id,
            success=True,
            stage="COMPLETED",
            message="Order successfully reserved, paid, and fulfilled",
            reservations=acquired_reservation_ids,
            payment_status=payment.status.value,
            fulfillment_status=fulfillment.status.value,
            compensated=False,
        )
