from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.schemas.reservation import (
    ReservationCreateRequest,
    ReservationReleaseRequest,
    ReservationResponse,
)
from stockguard.services.reservation_service import (
    ReservationService,
    ReservationNotFoundException,
    InvalidReservationStateException,
)
from stockguard.services.inventory_service import (
    ProductNotFoundException,
    InsufficientStockException,
)

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(req: ReservationCreateRequest, db: Session = Depends(get_db)):
    try:
        return ReservationService.create_reservation(db, req)
    except ProductNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientStockException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[ReservationResponse])
def list_reservations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return ReservationService.list_reservations(db, skip=skip, limit=limit)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(reservation_id: str, db: Session = Depends(get_db)):
    try:
        return ReservationService.get_reservation(db, reservation_id)
    except ReservationNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{reservation_id}/release", response_model=ReservationResponse)
def release_reservation(
    reservation_id: str,
    req: ReservationReleaseRequest = ReservationReleaseRequest(),
    db: Session = Depends(get_db),
):
    try:
        return ReservationService.release_reservation(db, reservation_id, reason=req.reason)
    except ReservationNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidReservationStateException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/expire-stale", status_code=status.HTTP_200_OK)
def trigger_expire_stale(db: Session = Depends(get_db)):
    count = ReservationService.expire_stale_reservations(db)
    return {"status": "ok", "expired_count": count}
