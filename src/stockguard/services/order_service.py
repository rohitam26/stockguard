import uuid
import logging
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.models.order import Order, OrderItem, OrderStatus
from stockguard.models.product import Product
from stockguard.schemas.order import OrderCreateRequest
from stockguard.services.outbox_service import OutboxService
from stockguard.services.inventory_service import ProductNotFoundException

logger = logging.getLogger("stockguard.order_service")


class OrderNotFoundException(Exception):
    pass


class InvalidOrderStateException(Exception):
    pass


class OrderService:
    @staticmethod
    def create_order(db: Session, req: OrderCreateRequest) -> Order:
        """
        Create an order in PENDING state with its items and calculate total amount.
        Guarantees idempotency if idempotency_key is provided.
        """
        if req.idempotency_key:
            existing = db.execute(
                select(Order).where(Order.idempotency_key == req.idempotency_key)
            ).scalar_one_or_none()
            if existing:
                logger.info("Idempotent order hit for key: %s", req.idempotency_key)
                return existing

        order_id = str(uuid.uuid4())
        order_number = f"ORD-{order_id[:8].upper()}"

        total_amount = Decimal("0.00")
        order_items: list[OrderItem] = []

        for item_req in req.items:
            product = db.execute(
                select(Product).where(Product.sku == item_req.sku, Product.is_active.is_(True))
            ).scalar_one_or_none()
            if not product:
                raise ProductNotFoundException(f"Active product with SKU '{item_req.sku}' not found.")

            subtotal = product.price * item_req.quantity
            total_amount += subtotal

            order_item = OrderItem(
                order_id=order_id,
                product_id=product.id,
                sku=product.sku,
                quantity=item_req.quantity,
                unit_price=product.price
            )
            order_items.append(order_item)

        order = Order(
            id=order_id,
            order_number=order_number,
            customer_id=req.customer_id,
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            currency=req.currency,
            idempotency_key=req.idempotency_key
        )
        db.add(order)
        db.flush()

        for oi in order_items:
            db.add(oi)

        OutboxService.create_message(
            db=db,
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "total_amount": str(order.total_amount),
                "currency": order.currency,
                "items": [
                    {"sku": oi.sku, "quantity": oi.quantity, "unit_price": str(oi.unit_price)}
                    for oi in order_items
                ]
            }
        )

        db.commit()
        db.refresh(order)
        logger.info("Created order %s (total: %s %s)", order.order_number, order.total_amount, order.currency)
        return order

    @staticmethod
    def get_order(db: Session, order_id: str) -> Order:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            raise OrderNotFoundException(f"Order '{order_id}' not found.")
        return order

    @staticmethod
    def list_orders(db: Session, skip: int = 0, limit: int = 100) -> list[Order]:
        query = select(Order).offset(skip).limit(limit).order_by(Order.created_at.desc())
        return list(db.execute(query).scalars().all())

    @staticmethod
    def update_order_status(
        db: Session,
        order_id: str,
        new_status: OrderStatus,
        failure_reason: str | None = None
    ) -> Order:
        order = OrderService.get_order(db, order_id)
        order.status = new_status
        if failure_reason:
            order.failure_reason = failure_reason

        OutboxService.create_message(
            db=db,
            event_type=f"order.status_changed",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={
                "order_id": order.id,
                "new_status": new_status.value,
                "failure_reason": failure_reason
            }
        )

        db.commit()
        db.refresh(order)
        return order
