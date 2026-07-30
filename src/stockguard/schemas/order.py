from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from stockguard.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64)
    quantity: int = Field(..., gt=0)


class OrderCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=2, max_length=64)
    items: list[OrderItemCreate] = Field(..., min_length=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    auto_pay: bool = Field(default=False, description="Automatically trigger simulated payment")


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: str
    status: OrderStatus
    total_amount: Decimal
    currency: str
    idempotency_key: str | None
    failure_reason: str | None
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
