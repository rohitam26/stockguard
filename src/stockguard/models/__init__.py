from stockguard.models.base import Base, TimestampMixin, utc_now
from stockguard.models.product import Product
from stockguard.models.inventory import InventoryItem
from stockguard.models.reservation import Reservation, ReservationStatus
from stockguard.models.order import Order, OrderItem, OrderStatus
from stockguard.models.payment import Payment, PaymentStatus
from stockguard.models.fulfillment import Fulfillment, FulfillmentStatus
from stockguard.models.outbox import OutboxMessage, OutboxStatus
from stockguard.models.event import ProcessedEvent
from stockguard.models.user import User, UserRole, RefreshToken

__all__ = [
    "Base",
    "TimestampMixin",
    "utc_now",
    "Product",
    "InventoryItem",
    "Reservation",
    "ReservationStatus",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Payment",
    "PaymentStatus",
    "Fulfillment",
    "FulfillmentStatus",
    "OutboxMessage",
    "OutboxStatus",
    "ProcessedEvent",
    "User",
    "UserRole",
    "RefreshToken",
]


def init_db(bind_engine):
    """Initializes all tables and database constraints."""
    Base.metadata.create_all(bind=bind_engine)
