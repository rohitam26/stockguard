from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.fulfillment import FulfillmentProcessRequest, FulfillmentResponse
from stockguard.services.fulfillment_service import FulfillmentService
from stockguard.services.order_service import OrderNotFoundException

router = APIRouter(prefix="/fulfillment", tags=["Fulfillment"])


@router.post("/order/{order_id}", response_model=FulfillmentResponse)
def initiate_fulfillment(
    order_id: str, req: FulfillmentProcessRequest | None = None, db: Session = Depends(get_db)
):
    try:
        return FulfillmentService.initiate_fulfillment(db, order_id, req)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/order/{order_id}", response_model=FulfillmentResponse)
def get_fulfillment_for_order(order_id: str, db: Session = Depends(get_db)):
    fulfillment = FulfillmentService.get_fulfillment_by_order(order_id=order_id, db=db)
    if not fulfillment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fulfillment not found.")
    return fulfillment
