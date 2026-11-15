import time
import uuid
import pytest
from starlette.testclient import TestClient


def test_atomic_reservation_and_idempotency(client: TestClient):
    sku = f"TEST-RES-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Atomic Buffer",
        "price": 10.00,
        "initial_stock": 10,
        "low_stock_threshold": 2
    })

    idempotency_key = f"key-idemp-{uuid.uuid4()}"

    # 1. Create reservation for 4 units
    res1 = client.post("/api/v1/reservations", json={
        "sku": sku,
        "quantity": 4,
        "ttl_seconds": 60,
        "idempotency_key": idempotency_key
    })
    assert res1.status_code == 201, res1.text
    res_data1 = res1.json()
    assert res_data1["quantity"] == 4
    assert res_data1["status"] == "ACTIVE"

    # Verify inventory state
    inv = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv["available_stock"] == 6
    assert inv["reserved_stock"] == 4

    # 2. Idempotent Retry: Submit exact same request with same idempotency key
    res2 = client.post("/api/v1/reservations", json={
        "sku": sku,
        "quantity": 4,
        "ttl_seconds": 60,
        "idempotency_key": idempotency_key
    })
    assert res2.status_code == 201
    res_data2 = res2.json()
    assert res_data2["id"] == res_data1["id"], "Idempotent request must return existing reservation"

    # Inventory must NOT be deducted again
    inv_after = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv_after["available_stock"] == 6
    assert inv_after["reserved_stock"] == 4


def test_reservation_insufficient_stock_rejection(client: TestClient):
    sku = f"TEST-OOS-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Limited Stock Item",
        "price": 50.00,
        "initial_stock": 2
    })

    # Try to reserve 5 units when only 2 exist
    res = client.post("/api/v1/reservations", json={
        "sku": sku,
        "quantity": 5,
        "ttl_seconds": 60,
        "idempotency_key": f"key-{uuid.uuid4()}"
    })
    assert res.status_code == 409
    assert "Cannot reserve 5 units" in res.json()["detail"]


def test_reservation_explicit_release(client: TestClient):
    sku = f"TEST-REL-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Releasable Item",
        "price": 100.00,
        "initial_stock": 10
    })

    # Reserve 3 units
    res = client.post("/api/v1/reservations", json={
        "sku": sku,
        "quantity": 3,
        "ttl_seconds": 60,
        "idempotency_key": f"key-{uuid.uuid4()}"
    })
    res_id = res.json()["id"]

    # Available: 7, Reserved: 3
    inv1 = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv1["available_stock"] == 7
    assert inv1["reserved_stock"] == 3

    # Release reservation
    res_rel = client.post(f"/api/v1/reservations/{res_id}/release", json={
        "reason": "Customer abandoned checkout"
    })
    assert res_rel.status_code == 200
    assert res_rel.json()["status"] == "RELEASED"

    # Available must be restored to 10, Reserved to 0
    inv2 = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv2["available_stock"] == 10
    assert inv2["reserved_stock"] == 0


def test_reservation_auto_expiry_sweep(client: TestClient):
    sku = f"TEST-EXP-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Expiring Item",
        "price": 20.00,
        "initial_stock": 10
    })

    # Reserve with 1 second TTL
    res = client.post("/api/v1/reservations", json={
        "sku": sku,
        "quantity": 4,
        "ttl_seconds": 1,
        "idempotency_key": f"key-exp-{uuid.uuid4()}"
    })
    res_id = res.json()["id"]

    inv1 = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv1["available_stock"] == 6

    # Wait for TTL to elapse
    time.sleep(1.2)

    # Trigger expire stale reservations sweep
    res_sweep = client.post("/api/v1/reservations/expire-stale")
    assert res_sweep.status_code == 200
    assert res_sweep.json()["expired_count"] >= 1

    # Check reservation status
    res_check = client.get(f"/api/v1/reservations/{res_id}").json()
    assert res_check["status"] == "EXPIRED"

    # Check available inventory was restored
    inv2 = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv2["available_stock"] == 10
    assert inv2["reserved_stock"] == 0
