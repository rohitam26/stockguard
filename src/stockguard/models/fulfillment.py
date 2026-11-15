import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class FulfillmentStatus(str, Enum):
    PENDING = "PENDING"
    PACKING = "PACKING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Fulfillment(Base, TimestampMixin):
    __tablename__ = "fulfillments"

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
    status: Mapped[FulfillmentStatus] = mapped_column(
        SQLEnum(FulfillmentStatus, native_enum=False, length=20),
        default=FulfillmentStatus.PENDING,
        nullable=False,
        index=True
    )
    tracking_number: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=True
    )
    carrier: Mapped[str | None] = mapped_column(
        String(64),
        default="SIM_CARRIER",
        nullable=True
    )
    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Relationship
    order = relationship("Order", back_populates="fulfillment")
