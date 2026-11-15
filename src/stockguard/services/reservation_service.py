import logging
from datetime import timedelta
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from stockguard.models.base import utc_now
from stockguard.models.inventory import InventoryItem
from stockguard.models.product import Product
from stockguard.models.reservation import Reservation, ReservationStatus
from stockguard.schemas.reservation import ReservationCreateRequest
from stockguard.services.outbox_service import OutboxService
from stockguard.services.inventory_service import (
    ProductNotFoundException,
    InsufficientStockException
)

logger = logging.getLogger("stockguard.reservation_service")


class ReservationNotFoundException(Exception):
    pass


class InvalidReservationStateException(Exception):
    pass


class ReservationService:
    @staticmethod
    def create_reservation(db: Session, req: ReservationCreateRequest) -> Reservation:
        """
        Atomically reserve inventory with idempotency guarantee and negative stock prevention.
        """
        # 1. Idempotency Check: Return existing reservation if idempotency_key was already used
        existing = db.execute(
            select(Reservation).where(Reservation.idempotency_key == req.idempotency_key)
        ).scalar_one_or_none()
        if existing:
            logger.info("Idempotent reservation hit for key: %s", req.idempotency_key)
            return existing

        # 2. Check if product exists
        product = db.execute(
            select(Product).where(Product.sku == req.sku, Product.is_active.is_(True))
        ).scalar_one_or_none()
        if not product:
            raise ProductNotFoundException(f"Active product with SKU '{req.sku}' not found.")

        # 3. Atomic conditional decrement of available stock and increment of reserved stock
        # In SQL: UPDATE inventory_items SET available_stock = available_stock - :qty,
        #         reserved_stock = reserved_stock + :qty WHERE sku = :sku AND available_stock >= :qty
        # Rowcount will be 0 if available_stock < req.quantity, completely preventing race condition overselling!
        stmt = (
            update(InventoryItem)
            .where(
                InventoryItem.sku == req.sku,
                InventoryItem.available_stock >= req.quantity
            )
            .values(
                available_stock=InventoryItem.available_stock - req.quantity,
                reserved_stock=InventoryItem.reserved_stock + req.quantity,
                version=InventoryItem.version + 1
            )
        )
        result = db.execute(stmt)

        if result.rowcount == 0:
            # Query current stock to furnish detailed error message
            curr_inv = db.execute(
                select(InventoryItem).where(InventoryItem.sku == req.sku)
            ).scalar_one_or_none()
            curr_avail = curr_inv.available_stock if curr_inv else 0
            raise InsufficientStockException(
                f"Cannot reserve {req.quantity} units of '{req.sku}'. Only {curr_avail} units available."
            )

        # 4. Create Reservation Record
        now = utc_now()
        expires_at = now + timedelta(seconds=req.ttl_seconds)
        reservation = Reservation(
            idempotency_key=req.idempotency_key,
            order_id=req.order_id,
            product_id=product.id,
            sku=req.sku,
            quantity=req.quantity,
            status=ReservationStatus.ACTIVE,
            expires_at=expires_at
        )
        db.add(reservation)
        db.flush()

        # 5. Transactional Outbox Message
        OutboxService.create_message(
            db=db,
            event_type="reservation.created",
            aggregate_type="reservation",
            aggregate_id=reservation.id,
            payload={
                "reservation_id": reservation.id,
                "idempotency_key": reservation.idempotency_key,
                "order_id": reservation.order_id,
                "sku": reservation.sku,
                "quantity": reservation.quantity,
                "expires_at": reservation.expires_at.isoformat()
            }
        )

        db.commit()
        db.refresh(reservation)
        logger.info(
            "Created reservation %s for %d units of SKU %s. Expires at: %s",
            reservation.id,
            reservation.quantity,
            reservation.sku,
            reservation.expires_at
        )
        return reservation

    @staticmethod
    def get_reservation(db: Session, reservation_id: str) -> Reservation:
        res = db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        ).scalar_one_or_none()
        if not res:
            raise ReservationNotFoundException(f"Reservation '{reservation_id}' not found.")
        return res

    @staticmethod
    def release_reservation(db: Session, reservation_id: str, reason: str = "Explicit release") -> Reservation:
        """
        Releases an active reservation and restores available stock.
        """
        res = ReservationService.get_reservation(db, reservation_id)
        if res.status != ReservationStatus.ACTIVE:
            raise InvalidReservationStateException(
                f"Cannot release reservation in '{res.status}' state."
            )

        # Atomically return reserved stock to available stock
        stmt = (
            update(InventoryItem)
            .where(InventoryItem.sku == res.sku)
            .values(
                available_stock=InventoryItem.available_stock + res.quantity,
                reserved_stock=InventoryItem.reserved_stock - res.quantity,
                version=InventoryItem.version + 1
            )
        )
        db.execute(stmt)

        res.status = ReservationStatus.RELEASED

        OutboxService.create_message(
            db=db,
            event_type="reservation.released",
            aggregate_type="reservation",
            aggregate_id=res.id,
            payload={
                "reservation_id": res.id,
                "sku": res.sku,
                "quantity": res.quantity,
                "reason": reason
            }
        )

        db.commit()
        db.refresh(res)
        logger.info("Released reservation %s for SKU %s (qty %d)", res.id, res.sku, res.quantity)
        return res

    @staticmethod
    def confirm_reservation(db: Session, reservation_id: str) -> Reservation:
        """
        Transitions reservation to CONFIRMED and moves reserved stock to allocated stock.
        """
        res = ReservationService.get_reservation(db, reservation_id)
        if res.status != ReservationStatus.ACTIVE:
            raise InvalidReservationStateException(
                f"Cannot confirm reservation in '{res.status}' state."
            )

        stmt = (
            update(InventoryItem)
            .where(InventoryItem.sku == res.sku)
            .values(
                reserved_stock=InventoryItem.reserved_stock - res.quantity,
                allocated_stock=InventoryItem.allocated_stock + res.quantity,
                version=InventoryItem.version + 1
            )
        )
        db.execute(stmt)

        res.status = ReservationStatus.CONFIRMED

        OutboxService.create_message(
            db=db,
            event_type="reservation.confirmed",
            aggregate_type="reservation",
            aggregate_id=res.id,
            payload={
                "reservation_id": res.id,
                "sku": res.sku,
                "quantity": res.quantity
            }
        )

        db.commit()
        db.refresh(res)
        logger.info("Confirmed reservation %s for SKU %s (allocated %d)", res.id, res.sku, res.quantity)
        return res

    @staticmethod
    def expire_stale_reservations(db: Session) -> int:
        """
        Background cleaner: Scans and expires all ACTIVE reservations past their expiration timestamp.
        """
        now = utc_now()
        stale_reservations = list(db.execute(
            select(Reservation).where(
                Reservation.status == ReservationStatus.ACTIVE,
                Reservation.expires_at <= now
            )
        ).scalars().all())

        count = 0
        for res in stale_reservations:
            try:
                # Return stock to available
                stmt = (
                    update(InventoryItem)
                    .where(InventoryItem.sku == res.sku)
                    .values(
                        available_stock=InventoryItem.available_stock + res.quantity,
                        reserved_stock=InventoryItem.reserved_stock - res.quantity,
                        version=InventoryItem.version + 1
                    )
                )
                db.execute(stmt)
                res.status = ReservationStatus.EXPIRED

                OutboxService.create_message(
                    db=db,
                    event_type="reservation.expired",
                    aggregate_type="reservation",
                    aggregate_id=res.id,
                    payload={
                        "reservation_id": res.id,
                        "sku": res.sku,
                        "quantity": res.quantity,
                        "expired_at": now.isoformat()
                    }
                )
                count += 1
            except Exception as e:
                logger.error("Failed to expire reservation %s: %s", res.id, e)

        if count > 0:
            db.commit()
            logger.info("Expired %d stale reservations", count)
        return count
