import uuid
from enum import Enum
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, ForeignKey, CheckConstraint, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    RESERVING = "RESERVING"
    RESERVED = "RESERVED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    FULFILLING = "FULFILLING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, native_enum=False, length=20),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship(
        "Payment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    fulfillment = relationship(
        "Fulfillment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="chk_order_total_amount_non_negative"),
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_item_unit_price_non_negative"),
    )
