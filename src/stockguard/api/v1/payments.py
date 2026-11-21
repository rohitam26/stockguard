from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.payment import PaymentProcessRequest, PaymentResponse
from stockguard.services.payment_service import PaymentService
from stockguard.services.order_service import OrderNotFoundException

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/process", response_model=PaymentResponse)
def process_payment(req: PaymentProcessRequest, db: Session = Depends(get_db)):
    try:
        return PaymentService.process_payment(db, req)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/order/{order_id}", response_model=PaymentResponse)
def get_payment_for_order(order_id: str, db: Session = Depends(get_db)):
    payment = PaymentService.get_payment_by_order(db, order_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found."
        )
    return payment
