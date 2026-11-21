import random
import uuid
from locust import HttpUser, task, between


class StockGuardLoadUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        """User registration and authentication session setup."""
        self.email = f"loaduser_{uuid.uuid4().hex[:10]}@stockguard.test"
        self.password = "LoadTestPass123!"
        self.token = None

        # Register
        reg_resp = self.client.post("/api/v1/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Locust Load Tester",
            "role": "CUSTOMER"
        })

        # Login
        if reg_resp.status_code in (200, 201):
            login_resp = self.client.post("/api/v1/auth/login", json={
                "email": self.email,
                "password": self.password
            })
            if login_resp.status_code == 200:
                self.token = login_resp.json().get("access_token")

        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.known_skus = [
            "LAPTOP-PRO-16",
            "DISPLAY-4K-32",
            "KEYBOARD-MECH",
            "MOUSE-PRECISION",
            "HEADSET-ANC",
            "CABLE-TB4-2M"
        ]

    @task(6)
    def browse_products(self):
        """Task 1: Catalog browsing."""
        self.client.get("/api/v1/products", headers=self.headers, name="/api/v1/products")

    @task(4)
    def check_inventory(self):
        """Task 2: Inventory level checks."""
        self.client.get("/api/v1/inventory", headers=self.headers, name="/api/v1/inventory")

    @task(3)
    def make_reservation(self):
        """Task 3: Concurrent atomic reservation attempt."""
        sku = random.choice(self.known_skus)
        idempotency_key = f"locust-res-{uuid.uuid4()}"
        with self.client.post(
            "/api/v1/reservations",
            json={"sku": sku, "quantity": 1, "ttl_seconds": 300, "idempotency_key": idempotency_key},
            headers=self.headers,
            name="/api/v1/reservations",
            catch_response=True
        ) as resp:
            # 201 is success, 409 is expected when stock exhausted (concurrency control)
            if resp.status_code in (201, 409):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def create_and_checkout_order(self):
        """Task 4: Order placement and Saga checkout execution."""
        sku = random.choice(self.known_skus)
        order_resp = self.client.post(
            "/api/v1/orders",
            json={
                "customer_id": self.email,
                "items": [{"sku": sku, "quantity": 1}],
                "auto_pay": False
            },
            headers=self.headers,
            name="/api/v1/orders [create]"
        )

        if order_resp.status_code == 201:
            order_data = order_resp.json()
            order_id = order_data.get("id")
            if order_id:
                with self.client.post(
                    f"/api/v1/orders/{order_id}/checkout",
                    params={"payment_method": "CREDIT_CARD", "simulate_failure": False},
                    headers=self.headers,
                    name="/api/v1/orders/{id}/checkout",
                    catch_response=True
                ) as checkout_resp:
                    if checkout_resp.status_code in (200, 409):
                        checkout_resp.success()
                    else:
                        checkout_resp.failure(f"Checkout error: {checkout_resp.status_code}")
