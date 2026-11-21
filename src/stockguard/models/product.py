import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Explicit foreign_keys to eliminate join ambiguity
    inventory = relationship(
        "InventoryItem",
        back_populates="product",
        primaryjoin="Product.id == InventoryItem.product_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reservations = relationship(
        "Reservation", back_populates="product", primaryjoin="Product.id == Reservation.product_id"
    )

    __table_args__ = (CheckConstraint("price >= 0", name="chk_product_price_non_negative"),)
