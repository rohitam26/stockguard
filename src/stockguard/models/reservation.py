import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, CheckConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class ReservationStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CONFIRMED = "CONFIRMED"


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    order_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        SQLEnum(ReservationStatus, native_enum=False, length=20),
        default=ReservationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Relationships
    product = relationship(
        "Product", back_populates="reservations", primaryjoin="Product.id == Reservation.product_id"
    )

    __table_args__ = (CheckConstraint("quantity > 0", name="chk_reservation_quantity_positive"),)
