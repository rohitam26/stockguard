from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.order import OrderCreateRequest, OrderResponse
from stockguard.services.order_service import (
    OrderService,
    OrderNotFoundException
)
from stockguard.services.inventory_service import ProductNotFoundException
from stockguard.services.saga_orchestrator import SagaOrchestrator

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(req: OrderCreateRequest, db: Session = Depends(get_db)):
    try:
        order = OrderService.create_order(db, req)
        if req.auto_pay:
            # Trigger saga orchestrator
            SagaOrchestrator.execute_order_checkout(db, order.id)
            db.refresh(order)
        return order
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[OrderResponse])
def list_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return OrderService.list_orders(db, skip=skip, limit=limit)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    try:
        return OrderService.get_order(db, order_id)
    except OrderNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{order_id}/checkout")
def checkout_order(
    order_id: str,
    payment_method: str = "CREDIT_CARD",
    simulate_failure: bool = False,
    db: Session = Depends(get_db)
):
    try:
        result = SagaOrchestrator.execute_order_checkout(
            db=db,
            order_id=order_id,
            payment_method=payment_method,
            simulate_payment_failure=simulate_failure
        )
        return result.to_dict()
    except OrderNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
