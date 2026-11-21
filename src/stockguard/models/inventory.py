import uuid
from sqlalchemy import String, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stockguard.models.base import Base, TimestampMixin


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("products.sku", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    available_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allocated_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Explicit primaryjoin
    product = relationship(
        "Product", back_populates="inventory", primaryjoin="Product.id == InventoryItem.product_id"
    )

    __table_args__ = (
        CheckConstraint("available_stock >= 0", name="chk_inventory_available_non_negative"),
        CheckConstraint("reserved_stock >= 0", name="chk_inventory_reserved_non_negative"),
        CheckConstraint("allocated_stock >= 0", name="chk_inventory_allocated_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="chk_inventory_threshold_non_negative"),
    )

    @property
    def total_stock(self) -> int:
        return self.available_stock + self.reserved_stock + self.allocated_stock

    @property
    def is_low_stock(self) -> bool:
        return self.available_stock <= self.low_stock_threshold
