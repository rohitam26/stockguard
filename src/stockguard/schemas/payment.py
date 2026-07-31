from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from stockguard.models.payment import PaymentStatus


class PaymentProcessRequest(BaseModel):
    order_id: str = Field(..., description="Target order ID")
    payment_method: str = Field(default="CREDIT_CARD", max_length=64)
    simulate_failure: bool = Field(default=False, description="Simulate payment failure for testing")
    failure_reason: str | None = Field(default=None, max_length=255)


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    transaction_id: str | None
    payment_method: str
    failure_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
