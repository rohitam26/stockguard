from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from stockguard.services.inventory_service import (
    InventoryService,
    ProductNotFoundException,
    SkuAlreadyExistsException
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(req: ProductCreate, db: Session = Depends(get_db)):
    try:
        product = InventoryService.create_product(db, req)
        return product
    except SkuAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=list[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    return InventoryService.list_products(db, skip=skip, limit=limit, active_only=active_only)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, db: Session = Depends(get_db)):
    try:
        # Check by ID first, then by SKU
        try:
            return InventoryService.get_product_by_id(db, product_id)
        except ProductNotFoundException:
            return InventoryService.get_product_by_sku(db, product_id)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: str, req: ProductUpdate, db: Session = Depends(get_db)):
    try:
        return InventoryService.update_product(db, product_id, req)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
