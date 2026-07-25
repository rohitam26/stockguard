import uuid
from enum import Enum
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, CheckConstraint, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, native_enum=False, length=20),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=True
    )
    payment_method: Mapped[str] = mapped_column(
        String(64),
        default="SIMULATED_CARD",
        nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Relationship
    order = relationship("Order", back_populates="payment")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="chk_payment_amount_non_negative"),
    )
