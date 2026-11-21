from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.inventory import InventoryAdjustRequest, InventoryResponse
from stockguard.services.inventory_service import (
    InventoryService,
    ProductNotFoundException,
    InsufficientStockException,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=list[InventoryResponse])
def list_inventory(skip: int = 0, limit: int = 500, db: Session = Depends(get_db)):
    return InventoryService.list_inventory(db, skip=skip, limit=limit)


@router.get("/{sku}", response_model=InventoryResponse)
def get_inventory_by_sku(sku: str, db: Session = Depends(get_db)):
    try:
        return InventoryService.get_inventory_by_sku(db, sku)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/adjust", response_model=InventoryResponse)
def adjust_inventory(req: InventoryAdjustRequest, db: Session = Depends(get_db)):
    try:
        return InventoryService.adjust_inventory(db, req)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientStockException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
