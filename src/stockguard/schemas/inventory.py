from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class InventoryAdjustRequest(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64, description="Product SKU to adjust")
    quantity_delta: int = Field(
        ..., description="Quantity delta (positive to restock, negative to deduct)"
    )
    reason: str = Field(
        ..., min_length=3, max_length=255, description="Auditable adjustment reason"
    )


class InventoryResponse(BaseModel):
    id: str
    product_id: str
    sku: str
    available_stock: int
    reserved_stock: int
    allocated_stock: int
    total_stock: int
    low_stock_threshold: int
    is_low_stock: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
