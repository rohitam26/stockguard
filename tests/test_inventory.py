import uuid
import pytest
from starlette.testclient import TestClient


def test_create_and_retrieve_product(client: TestClient):
    sku = f"TEST-SKU-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "sku": sku,
        "name": "Precision Mechanical Switch",
        "description": "High-durability linear switch",
        "price": 0.45,
        "initial_stock": 100,
        "low_stock_threshold": 15
    }

    # 1. Create product
    res = client.post("/api/v1/products", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["sku"] == sku
    assert data["name"] == payload["name"]

    # 2. Duplicate SKU rejected with 409
    res_dup = client.post("/api/v1/products", json=payload)
    assert res_dup.status_code == 409

    # 3. Retrieve product by SKU
    res_get = client.get(f"/api/v1/products/{sku}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == data["id"]

    # 4. Verify initial inventory was created
    res_inv = client.get(f"/api/v1/inventory/{sku}")
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["available_stock"] == 100
    assert inv_data["reserved_stock"] == 0
    assert inv_data["total_stock"] == 100
    assert inv_data["is_low_stock"] is False


def test_inventory_adjustment_and_negative_stock_rejection(client: TestClient):
    sku = f"TEST-ADJ-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Stock Level Indicator",
        "price": 25.00,
        "initial_stock": 20,
        "low_stock_threshold": 5
    })

    # Restock by +15
    res_restock = client.post("/api/v1/inventory/adjust", json={
        "sku": sku,
        "quantity_delta": 15,
        "reason": "Replenishment batch #992"
    })
    assert res_restock.status_code == 200
    assert res_restock.json()["available_stock"] == 35

    # Valid deduction of -10
    res_deduct = client.post("/api/v1/inventory/adjust", json={
        "sku": sku,
        "quantity_delta": -10,
        "reason": "Sample distribution"
    })
    assert res_deduct.status_code == 200
    assert res_deduct.json()["available_stock"] == 25

    # Insufficient stock deduction: try to deduct 50 when only 25 available
    res_over = client.post("/api/v1/inventory/adjust", json={
        "sku": sku,
        "quantity_delta": -50,
        "reason": "Exorbitant deduction attempt"
    })
    assert res_over.status_code == 400
    assert "Insufficient stock" in res_over.json()["detail"]

    # Verify inventory remained 25 (did not become negative)
    res_final = client.get(f"/api/v1/inventory/{sku}")
    assert res_final.json()["available_stock"] == 25
