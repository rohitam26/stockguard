import uuid
import pytest
from starlette.testclient import TestClient


def test_order_creation_and_successful_saga(client: TestClient):
    sku1 = f"SAGA-ITEM1-{uuid.uuid4().hex[:6].upper()}"
    sku2 = f"SAGA-ITEM2-{uuid.uuid4().hex[:6].upper()}"

    client.post("/api/v1/products", json={"sku": sku1, "name": "Item 1", "price": 40.00, "initial_stock": 10})
    client.post("/api/v1/products", json={"sku": sku2, "name": "Item 2", "price": 10.00, "initial_stock": 10})

    # Create Order
    order_res = client.post("/api/v1/orders", json={
        "customer_id": "cust-bob-101",
        "items": [
            {"sku": sku1, "quantity": 2},
            {"sku": sku2, "quantity": 3}
        ],
        "idempotency_key": f"order-idemp-{uuid.uuid4()}"
    })
    assert order_res.status_code == 201
    order_data = order_res.json()
    order_id = order_data["id"]
    assert float(order_data["total_amount"]) == (2 * 40.00) + (3 * 10.00)  # 110.00
    assert order_data["status"] == "PENDING"

    # Execute Saga Checkout
    saga_res = client.post(f"/api/v1/orders/{order_id}/checkout?simulate_failure=false")
    assert saga_res.status_code == 200
    saga_data = saga_res.json()
    assert saga_data["success"] is True
    assert saga_data["stage"] == "COMPLETED"
    assert saga_data["compensated"] is False

    # Check order is COMPLETED
    updated_order = client.get(f"/api/v1/orders/{order_id}").json()
    assert updated_order["status"] == "COMPLETED"

    # Check stock was moved from available to allocated
    inv1 = client.get(f"/api/v1/inventory/{sku1}").json()
    assert inv1["available_stock"] == 8
    assert inv1["allocated_stock"] == 2

    inv2 = client.get(f"/api/v1/inventory/{sku2}").json()
    assert inv2["available_stock"] == 7
    assert inv2["allocated_stock"] == 3


def test_saga_compensation_on_payment_failure(client: TestClient):
    sku = f"SAGA-FAIL-PAY-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v1/products", json={"sku": sku, "name": "Compensation Test Item", "price": 99.00, "initial_stock": 5})

    # Create Order
    order_res = client.post("/api/v1/orders", json={
        "customer_id": "cust-declined-55",
        "items": [{"sku": sku, "quantity": 3}]
    })
    order_id = order_res.json()["id"]

    # Execute Saga with simulated payment failure
    saga_res = client.post(f"/api/v1/orders/{order_id}/checkout?simulate_failure=true")
    assert saga_res.status_code == 200
    saga_data = saga_res.json()
    assert saga_data["success"] is False
    assert saga_data["stage"] == "PAYMENT"
    assert saga_data["compensated"] is True

    # Order must be CANCELLED with reason
    updated_order = client.get(f"/api/v1/orders/{order_id}").json()
    assert updated_order["status"] == "CANCELLED"
    assert "Payment declined" in updated_order["failure_reason"]

    # Verify inventory was completely restored by compensating transaction
    inv = client.get(f"/api/v1/inventory/{sku}").json()
    assert inv["available_stock"] == 5, "Compensating transaction must restore reserved stock"
    assert inv["reserved_stock"] == 0
    assert inv["allocated_stock"] == 0


def test_saga_compensation_on_insufficient_stock(client: TestClient):
    sku_avail = f"SAGA-STOCK-OK-{uuid.uuid4().hex[:6].upper()}"
    sku_depleted = f"SAGA-STOCK-DEP-{uuid.uuid4().hex[:6].upper()}"

    client.post("/api/v1/products", json={"sku": sku_avail, "name": "Item Available", "price": 10.00, "initial_stock": 5})
    client.post("/api/v1/products", json={"sku": sku_depleted, "name": "Item Low", "price": 10.00, "initial_stock": 1})

    # Order requesting 2 of each (second item only has 1)
    order_res = client.post("/api/v1/orders", json={
        "customer_id": "cust-out-of-stock",
        "items": [
            {"sku": sku_avail, "quantity": 2},
            {"sku": sku_depleted, "quantity": 2}
        ]
    })
    order_id = order_res.json()["id"]

    saga_res = client.post(f"/api/v1/orders/{order_id}/checkout")
    saga_data = saga_res.json()
    assert saga_data["success"] is False
    assert saga_data["stage"] == "RESERVATION"
    assert saga_data["compensated"] is True

    # Check order status is FAILED
    updated_order = client.get(f"/api/v1/orders/{order_id}").json()
    assert updated_order["status"] == "FAILED"

    # Compensation must have released the reservation acquired for sku_avail!
    inv_avail = client.get(f"/api/v1/inventory/{sku_avail}").json()
    assert inv_avail["available_stock"] == 5, "Compensation must release partial reservation"
    assert inv_avail["reserved_stock"] == 0
