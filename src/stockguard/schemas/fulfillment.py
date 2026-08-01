from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from stockguard.models.fulfillment import FulfillmentStatus


class FulfillmentProcessRequest(BaseModel):
    carrier: str = Field(default="FAST_SHIP", max_length=64)
    tracking_number: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=500)


class FulfillmentResponse(BaseModel):
    id: str
    order_id: str
    status: FulfillmentStatus
    tracking_number: str | None
    carrier: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
