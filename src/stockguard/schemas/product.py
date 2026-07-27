from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64, description="Unique Stock Keeping Unit")
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    description: str | None = Field(default=None, max_length=2000, description="Product description")
    price: Decimal = Field(..., ge=0, decimal_places=2, description="Price must be non-negative")
    initial_stock: int = Field(default=0, ge=0, description="Initial available inventory")
    low_stock_threshold: int = Field(default=10, ge=0, description="Low stock alert threshold")


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_active: bool | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
