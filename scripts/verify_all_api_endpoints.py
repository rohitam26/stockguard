import requests
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_api_verification():
    results = []

    def check(name, method, url, status_code, json_data=None):
        try:
            r = requests.request(method, f"{BASE_URL}{url}", json=json_data, timeout=5)
            passed = (r.status_code == status_code)
            results.append({
                "name": name,
                "method": method,
                "url": url,
                "expected": status_code,
                "actual": r.status_code,
                "passed": passed,
                "response": r.json() if "application/json" in r.headers.get("content-type", "") else r.text[:100]
            })
            status_str = "PASS" if passed else "FAIL"
            print(f"[{status_str}] {method} {url} -> {r.status_code} (Expected {status_code})")
            return r
        except Exception as e:
            results.append({
                "name": name,
                "method": method,
                "url": url,
                "expected": status_code,
                "actual": "ERROR",
                "passed": False,
                "response": str(e)
            })
            print(f"[FAIL] {method} {url} -> ERROR: {e}")
            return None

    print("=== VERIFYING ALL 22 API ENDPOINTS ===")

    # 1. Health
    check("Health Check", "GET", "/api/v1/health", 200)

    # 2. Products
    sku = f"AUDIT-SKU-{uuid.uuid4().hex[:6].upper()}"
    p_res = check("Create Product", "POST", "/api/v1/products", 201, {
        "sku": sku,
        "name": "Audit Tracked Component",
        "description": "Component for complete API audit",
        "price": 149.99,
        "initial_stock": 25,
        "low_stock_threshold": 5
    })
    p_id = p_res.json()["id"] if p_res and p_res.status_code == 201 else ""

    check("List Products", "GET", "/api/v1/products", 200)
    check("Get Product by ID", "GET", f"/api/v1/products/{p_id}", 200)
    check("Get Product by SKU", "GET", f"/api/v1/products/{sku}", 200)
    check("Update Product", "PUT", f"/api/v1/products/{p_id}", 200, {
        "name": "Audit Tracked Component (Updated)",
        "price": 159.99
    })

    # 3. Inventory
    check("List Inventory", "GET", "/api/v1/inventory", 200)
    check("Get Inventory by SKU", "GET", f"/api/v1/inventory/{sku}", 200)
    check("Adjust Inventory (Restock)", "POST", "/api/v1/inventory/adjust", 200, {
        "sku": sku,
        "quantity_delta": 10,
        "reason": "Audit inventory test restock"
    })
    check("Adjust Inventory (Invalid negative stock rejection)", "POST", "/api/v1/inventory/adjust", 400, {
        "sku": sku,
        "quantity_delta": -100,
        "reason": "Audit excessive deduction"
    })

    # 4. Reservations
    res_key = f"audit-res-key-{uuid.uuid4()}"
    r_res = check("Create Reservation", "POST", "/api/v1/reservations", 201, {
        "sku": sku,
        "quantity": 3,
        "ttl_seconds": 60,
        "idempotency_key": res_key
    })
    res_id = r_res.json()["id"] if r_res and r_res.status_code == 201 else ""

    check("Idempotent Duplicate Reservation", "POST", "/api/v1/reservations", 201, {
        "sku": sku,
        "quantity": 3,
        "ttl_seconds": 60,
        "idempotency_key": res_key
    })
    check("Get Reservation", "GET", f"/api/v1/reservations/{res_id}", 200)
    check("Release Reservation", "POST", f"/api/v1/reservations/{res_id}/release", 200, {
        "reason": "Audit release verification"
    })
    check("Expire Stale Reservations Sweep", "POST", "/api/v1/reservations/expire-stale", 200)

    # 5. Orders & Saga
    ord_key = f"audit-order-key-{uuid.uuid4()}"
    o_res = check("Create Order", "POST", "/api/v1/orders", 201, {
        "customer_id": "cust-audit-tester",
        "items": [{"sku": sku, "quantity": 2}],
        "idempotency_key": ord_key
    })
    ord_id = o_res.json()["id"] if o_res and o_res.status_code == 201 else ""

    check("List Orders", "GET", "/api/v1/orders", 200)
    check("Get Order by ID", "GET", f"/api/v1/orders/{ord_id}", 200)
    check("Order Checkout Saga (Success)", "POST", f"/api/v1/orders/{ord_id}/checkout?simulate_failure=false", 200)

    # Order Checkout Saga with Simulated Failure (Compensation)
    ord2_res = check("Create Order 2 for Compensation", "POST", "/api/v1/orders", 201, {
        "customer_id": "cust-compensation-tester",
        "items": [{"sku": sku, "quantity": 1}]
    })
    ord2_id = ord2_res.json()["id"]
    check("Order Checkout Saga (Simulated Failure & Compensation)", "POST", f"/api/v1/orders/{ord2_id}/checkout?simulate_failure=true", 200)

    # 6. Payment Direct
    check("Get Payment for Order", "GET", f"/api/v1/payments/order/{ord_id}", 200)

    # 7. Fulfillment Direct
    check("Get Fulfillment for Order", "GET", f"/api/v1/fulfillment/order/{ord_id}", 200)

    # 8. Outbox
    check("List Outbox Messages", "GET", "/api/v1/outbox", 200)
    check("Process Outbox Messages", "POST", "/api/v1/outbox/process", 200)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"\nAPI Verification Summary: {passed_count}/{total} Passed")
    return results

if __name__ == "__main__":
    run_api_verification()
