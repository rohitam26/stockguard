from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from stockguard.models.reservation import ReservationStatus


class ReservationCreateRequest(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64, description="Product SKU")
    quantity: int = Field(..., gt=0, description="Quantity to reserve (must be > 0)")
    order_id: str | None = Field(default=None, description="Associated order ID if any")
    ttl_seconds: int = Field(
        default=600, gt=0, le=86400, description="TTL in seconds (default 10 minutes)"
    )
    idempotency_key: str = Field(
        ..., min_length=8, max_length=128, description="Unique client key for idempotency"
    )


class ReservationReleaseRequest(BaseModel):
    reason: str = Field(default="Manual cancellation", max_length=255)


class ReservationResponse(BaseModel):
    id: str
    idempotency_key: str
    order_id: str | None
    product_id: str
    sku: str
    quantity: int
    status: ReservationStatus
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
