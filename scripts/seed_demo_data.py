import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from stockguard.database import get_session_factory
from stockguard.schemas.product import ProductCreate
from stockguard.schemas.reservation import ReservationCreateRequest
from stockguard.schemas.order import OrderCreateRequest, OrderItemCreate
from stockguard.services.inventory_service import InventoryService
from stockguard.services.reservation_service import ReservationService
from stockguard.services.order_service import OrderService
from stockguard.services.saga_orchestrator import SagaOrchestrator
from stockguard.messaging.outbox_worker import OutboxWorker

def seed():
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        print("Seeding catalog products...")
        catalog = [
            ("LAPTOP-PRO-16", "MacBook Pro M3 16-inch 36GB", "High-performance developer workstation", 2499.00, 25, 5),
            ("DISPLAY-4K-32", "UltraFine 32-inch 4K HDR Monitor", "Color-accurate professional IPS panel", 799.50, 18, 4),
            ("KEYBOARD-MECH", "ErgoMechanical Wireless Keyboard", "Custom tactile switches with hot-swap PCB", 179.00, 40, 10),
            ("MOUSE-PRECISION", "Master Wireless Precision Mouse", "Ergonomic darkfield laser tracking mouse", 99.99, 30, 8),
            ("HEADSET-ANC", "AeroSound Pro Noise-Cancelling Headphones", "Studio grade lossless wireless audio", 349.00, 12, 3),
            ("DOCK-TB4-12P", "Thunderbolt 4 Multi-Port Pro Dock", "100W PD with dual 4K display output", 229.00, 6, 8), # Low stock!
            ("CABLE-TB4-2M", "Certified Thunderbolt 4 Braided Cable 2m", "40Gbps high-speed transmission cable", 49.00, 120, 20),
            ("CHAIR-ERGO-X", "Aeron Ergonomic Mesh Task Chair", "PostureFit SL dynamic lumbar support", 1195.00, 8, 2),
        ]

        created_prods = []
        for sku, name, desc, price, stock, threshold in catalog:
            try:
                p = InventoryService.create_product(
                    db,
                    ProductCreate(
                        sku=sku,
                        name=name,
                        description=desc,
                        price=price,
                        initial_stock=stock,
                        low_stock_threshold=threshold
                    )
                )
                created_prods.append(p)
                print(f"Created {sku} with {stock} units")
            except Exception as e:
                print(f"Product {sku} already exists or error: {e}")

        # Create realistic active reservations
        print("Seeding active reservations...")
        try:
            ReservationService.create_reservation(
                db,
                ReservationCreateRequest(
                    sku="LAPTOP-PRO-16",
                    quantity=2,
                    ttl_seconds=600,
                    idempotency_key="seed-res-laptop-01"
                )
            )
            ReservationService.create_reservation(
                db,
                ReservationCreateRequest(
                    sku="DISPLAY-4K-32",
                    quantity=1,
                    ttl_seconds=600,
                    idempotency_key="seed-res-display-01"
                )
            )
        except Exception as e:
            print("Reservation seed error:", e)

        # Create orders and execute sagas
        print("Seeding orders and executing Sagas...")
        try:
            o1 = OrderService.create_order(
                db,
                OrderCreateRequest(
                    customer_id="cust-enterprise-techcorp",
                    items=[
                        OrderItemCreate(sku="KEYBOARD-MECH", quantity=2),
                        OrderItemCreate(sku="MOUSE-PRECISION", quantity=2)
                    ],
                    idempotency_key="seed-order-001"
                )
            )
            SagaOrchestrator.execute_order_checkout(db, o1.id)
            print(f"Order {o1.order_number} completed via Saga checkout")

            o2 = OrderService.create_order(
                db,
                OrderCreateRequest(
                    customer_id="cust-design-studio",
                    items=[
                        OrderItemCreate(sku="HEADSET-ANC", quantity=1),
                        OrderItemCreate(sku="CABLE-TB4-2M", quantity=3)
                    ],
                    idempotency_key="seed-order-002"
                )
            )
            SagaOrchestrator.execute_order_checkout(db, o2.id)
            print(f"Order {o2.order_number} completed via Saga checkout")
        except Exception as e:
            print("Order seed error:", e)

        # Flush Outbox
        OutboxWorker.process_pending_messages(db, batch_size=200)
        print("Seeding completed successfully!")

if __name__ == "__main__":
    seed()
