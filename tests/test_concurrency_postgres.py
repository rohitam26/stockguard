import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import select
from stockguard.database import get_session_factory, is_postgresql
from stockguard.models.inventory import InventoryItem
from stockguard.models.product import Product
from stockguard.schemas.product import ProductCreate
from stockguard.schemas.reservation import ReservationCreateRequest
from stockguard.services.inventory_service import InventoryService, InsufficientStockException
from stockguard.services.reservation_service import ReservationService


def test_100_concurrent_reservations_against_postgresql():
    """
    CRITICAL REQUIREMENT:
    Create 5 units of available stock and issue 100 simultaneous reservation requests for one unit each.
    Verify:
    - No more than 5 reservations succeed.
    - Inventory never becomes negative.
    - Successful reservations total 5 units.
    - Final inventory is consistent.
    Must run against PostgreSQL.
    """
    assert is_postgresql() is True, "Concurrency test MUST run against PostgreSQL, not SQLite!"

    SessionFactory = get_session_factory()
    sku = f"CONCURRENCY-5-100-{uuid.uuid4().hex[:6].upper()}"

    # 1. Setup: Create Product with exactly 5 units of initial available stock
    with SessionFactory() as db:
        prod = InventoryService.create_product(
            db,
            ProductCreate(
                sku=sku,
                name="High Contention Flash Sale Item",
                price=99.99,
                initial_stock=5,
                low_stock_threshold=1
            )
        )
        assert prod is not None

        # Verify initial inventory in PostgreSQL
        inv_initial = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one()
        assert inv_initial.available_stock == 5
        assert inv_initial.reserved_stock == 0

    # 2. Concurrency Experiment: 100 Simultaneous Reservation Requests for 1 unit each
    total_requests = 100
    quantity_per_request = 1

    def make_reservation(req_index: int):
        idempotency_key = f"concurrency-{sku}-{req_index}-{uuid.uuid4()}"
        with SessionFactory() as local_db:
            try:
                res = ReservationService.create_reservation(
                    local_db,
                    ReservationCreateRequest(
                        sku=sku,
                        quantity=quantity_per_request,
                        ttl_seconds=300,
                        idempotency_key=idempotency_key
                    )
                )
                return {"success": True, "reservation_id": res.id, "error": None}
            except InsufficientStockException as e:
                return {"success": False, "reservation_id": None, "error": str(e)}
            except Exception as e:
                return {"success": False, "reservation_id": None, "error": f"Unexpected: {e}"}

    success_count = 0
    failure_count = 0
    errors = []

    # Execute 100 requests concurrently with 20 worker threads
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_reservation, i) for i in range(total_requests)]
        for f in as_completed(futures):
            res = f.result()
            if res["success"]:
                success_count += 1
            else:
                failure_count += 1
                errors.append(res["error"])

    # 3. Assertions & Verification
    # No more than 5 reservations succeed
    assert success_count == 5, f"Expected exactly 5 successful reservations, got {success_count}"
    assert failure_count == 95, f"Expected exactly 95 rejections, got {failure_count}"

    # 4. Deep Database State Audit in PostgreSQL
    with SessionFactory() as db:
        inv_final = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one()

        # Inventory never becomes negative
        assert inv_final.available_stock >= 0, f"Available stock became negative: {inv_final.available_stock}"
        assert inv_final.reserved_stock >= 0, f"Reserved stock became negative: {inv_final.reserved_stock}"

        # Exact stock values
        assert inv_final.available_stock == 0, f"Available stock should be 0, got {inv_final.available_stock}"
        assert inv_final.reserved_stock == 5, f"Reserved stock should be 5, got {inv_final.reserved_stock}"
        assert inv_final.total_stock == 5, f"Total stock should remain 5, got {inv_final.total_stock}"

    print(
        f"\n[CONCURRENCY AUDIT PASSED] 100 simultaneous requests against PostgreSQL: "
        f"{success_count} succeeded, {failure_count} rejected for insufficient stock. "
        f"Final stock: available=0, reserved=5. Negative inventory prevented."
    )
