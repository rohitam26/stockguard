import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from decimal import Decimal
import pytest
from sqlalchemy import select, text
from fastapi.testclient import TestClient

from stockguard.main import app
from stockguard.database import get_session_factory
from stockguard.models.outbox import OutboxMessage, OutboxStatus
from stockguard.models.product import Product
from stockguard.models.inventory import InventoryItem
from stockguard.models.order import Order, OrderItem, OrderStatus
from stockguard.models.event import ProcessedEvent
from stockguard.messaging.outbox_worker import OutboxWorker
from stockguard.messaging.consumer import RabbitMQConsumerWorker
from stockguard.messaging.rabbitmq import rabbitmq_client
from stockguard.services.saga_orchestrator import SagaOrchestrator
from stockguard.services.order_service import OrderService
from stockguard.schemas.order import OrderCreateRequest, OrderItemCreate

client = TestClient(app)


def test_outbox_worker_crash_recovery_of_stuck_messages():
    """
    CRASH RECOVERY TEST:
    Simulates an OutboxWorker process dying unexpectedly while processing messages.
    Messages left in PROCESSING state must be detected and safely recovered back to PENDING.
    """
    SessionFactory = get_session_factory()
    now = datetime.now(timezone.utc)
    stuck_time = now - timedelta(seconds=120)  # Stuck 2 minutes ago
    stuck_id = str(uuid.uuid4())

    with SessionFactory() as db:
        stuck_msg = OutboxMessage(
            id=stuck_id,
            event_type="test.crash_recovery",
            aggregate_type="test",
            aggregate_id=str(uuid.uuid4()),
            payload=json.dumps({"test": "crash_recovery_payload"}),
            status=OutboxStatus.PROCESSING,
            retry_count=0
        )
        db.add(stuck_msg)
        db.commit()

        # Update updated_at directly via SQL to simulate passage of time
        db.execute(
            text("UPDATE outbox_messages SET updated_at = :t WHERE id = :id"),
            {"t": stuck_time, "id": stuck_id}
        )
        db.commit()

    # Run Outbox Worker
    with SessionFactory() as db:
        recovered = OutboxWorker.recover_stuck_messages(db, stuck_timeout_seconds=60)
        assert recovered >= 1

        # Message should now be back to PENDING or processed
        msg = db.get(OutboxMessage, stuck_id)
        assert msg is not None
        assert msg.status in (OutboxStatus.PENDING, OutboxStatus.PUBLISHED)
        assert "Recovered from dead worker crash" in msg.last_error

        # Process pending messages until all are drained
        while OutboxWorker.process_pending_messages(db, batch_size=100) > 0:
            pass

        db.refresh(msg)
        assert msg.status == OutboxStatus.PUBLISHED


def test_poison_message_quarantine():
    """
    POISON MESSAGE TEST:
    Outbox message with corrupt/invalid JSON must be quarantined as FAILED immediately,
    preventing infinite crash loops and allowing valid subsequent messages to proceed.
    """
    SessionFactory = get_session_factory()
    valid_id = str(uuid.uuid4())
    poison_id = str(uuid.uuid4())

    with SessionFactory() as db:
        # Valid message
        valid_msg = OutboxMessage(
            id=valid_id,
            event_type="test.valid",
            aggregate_type="test",
            aggregate_id=str(uuid.uuid4()),
            payload=json.dumps({"valid": True}),
            status=OutboxStatus.PENDING
        )
        # Poison message (corrupt JSON)
        poison_msg = OutboxMessage(
            id=poison_id,
            event_type="test.poison",
            aggregate_type="test",
            aggregate_id=str(uuid.uuid4()),
            payload="<<NOT VALID JSON>>",
            status=OutboxStatus.PENDING
        )
        db.add(poison_msg)
        db.add(valid_msg)
        db.commit()

    with SessionFactory() as db:
        while OutboxWorker.process_pending_messages(db, batch_size=100) > 0:
            pass

        p_msg = db.get(OutboxMessage, poison_id)
        assert p_msg.status == OutboxStatus.FAILED
        assert "Poison pill quarantined" in p_msg.last_error

        v_msg = db.get(OutboxMessage, valid_id)
        assert v_msg.status == OutboxStatus.PUBLISHED


def test_consumer_message_deduplication():
    """
    CONSUMER DEDUPLICATION TEST:
    Delivering the same message twice must execute handler only once,
    with the duplicate recognized via processed_events table and acknowledged.
    """
    worker = RabbitMQConsumerWorker(queue_name="test.dedup.queue")
    mock_handler = MagicMock(return_value=True)
    worker.handler = mock_handler

    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 101
    mock_method.routing_key = "order.created"
    mock_props = MagicMock()
    mock_props.message_id = f"dedup-msg-{uuid.uuid4().hex[:8]}"
    mock_props.headers = {}
    body = json.dumps({"event": "order.created", "order_id": "ord-123"}).encode("utf-8")

    # First delivery: should process and ack
    worker.process_delivery(mock_ch, mock_method, mock_props, body)
    assert mock_handler.call_count == 1
    mock_ch.basic_ack.assert_called_with(delivery_tag=101)

    # Second delivery with identical message_id: should acknowledge duplicate without calling handler again
    mock_handler.reset_mock()
    mock_ch.reset_mock()
    worker.process_delivery(mock_ch, mock_method, mock_props, body)
    assert mock_handler.call_count == 0  # Did NOT re-process!
    mock_ch.basic_ack.assert_called_with(delivery_tag=101)  # Acknowledged cleanly


def test_consumer_malformed_json_rejection_to_dlq():
    """
    CONSUMER POISON MESSAGE TEST:
    Malformed unparseable body should trigger basic_nack(requeue=False) to route to DLQ.
    """
    worker = RabbitMQConsumerWorker(queue_name="test.poison.queue")
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 202
    mock_method.routing_key = "test.malformed"
    mock_props = MagicMock()
    mock_props.message_id = f"poison-{uuid.uuid4().hex[:8]}"
    mock_props.headers = {}

    worker.process_delivery(mock_ch, mock_method, mock_props, b"MALFORMED_BYTES_NOT_JSON")
    mock_ch.basic_nack.assert_called_with(delivery_tag=202, requeue=False)


def test_saga_compensation_on_payment_decline():
    """
    SAGA BACKWARD COMPENSATION TEST:
    Simulates checkout with payment failure.
    Must verify that all acquired stock holds are returned to available_stock with 0 orphan holds.
    """
    SessionFactory = get_session_factory()
    sku = f"SAGA-FAIL-{int(time.time()*1000)}"

    with SessionFactory() as db:
        prod = Product(
            id=str(uuid.uuid4()),
            sku=sku,
            name="Saga Fail Product",
            price=Decimal("49.99"),
            is_active=True
        )
        inv = InventoryItem(
            id=str(uuid.uuid4()),
            product_id=prod.id,
            sku=sku,
            available_stock=10,
            reserved_stock=0,
            allocated_stock=0
        )
        db.add(prod)
        db.add(inv)
        db.commit()

        # Create Order
        order = OrderService.create_order(db, OrderCreateRequest(
            customer_id="cust-saga-fail",
            items=[OrderItemCreate(sku=sku, quantity=4)],
            auto_pay=False
        ))
        order_id = order.id

    # Execute Saga with simulated payment failure
    with SessionFactory() as db:
        result = SagaOrchestrator.execute_order_checkout(
            db=db,
            order_id=order_id,
            payment_method="CREDIT_CARD",
            simulate_payment_failure=True
        )
        assert result.success is False
        assert result.stage == "PAYMENT"
        assert result.compensated is True

        # Check inventory is completely restored
        inv_after = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one()
        assert inv_after.available_stock == 10
        assert inv_after.reserved_stock == 0
        assert inv_after.allocated_stock == 0

        # Check order status is CANCELLED
        order_after = db.get(Order, order_id)
        assert order_after.status == OrderStatus.CANCELLED


def test_duplicate_checkout_idempotency():
    """
    CHECKOUT IDEMPOTENCY TEST:
    Calling checkout on an already completed order returns original completion state,
    without executing duplicate charges or stock modifications.
    """
    SessionFactory = get_session_factory()
    sku = f"IDEM-CHECKOUT-{int(time.time()*1000)}"

    with SessionFactory() as db:
        prod = Product(
            id=str(uuid.uuid4()),
            sku=sku,
            name="Idempotent Checkout Product",
            price=Decimal("15.00"),
            is_active=True
        )
        inv = InventoryItem(
            id=str(uuid.uuid4()),
            product_id=prod.id,
            sku=sku,
            available_stock=5,
            reserved_stock=0,
            allocated_stock=0
        )
        db.add(prod)
        db.add(inv)
        db.commit()

        order = OrderService.create_order(db, OrderCreateRequest(
            customer_id="cust-idem",
            items=[OrderItemCreate(sku=sku, quantity=2)],
            auto_pay=False
        ))
        order_id = order.id

    # First checkout (Success)
    with SessionFactory() as db:
        res1 = SagaOrchestrator.execute_order_checkout(db, order_id=order_id, simulate_payment_failure=False)
        assert res1.success is True
        assert res1.stage == "COMPLETED"

    # Second checkout on same order (Duplicate call)
    with SessionFactory() as db:
        res2 = SagaOrchestrator.execute_order_checkout(db, order_id=order_id, simulate_payment_failure=False)
        assert res2.success is True
        assert res2.stage == "COMPLETED"
        assert "idempotent" in res2.message.lower()

        # Confirm stock was only deducted once: available=3, allocated=2
        inv_check = db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalar_one()
        assert inv_check.available_stock == 3
        assert inv_check.allocated_stock == 2
        assert inv_check.reserved_stock == 0


def test_health_liveness_readiness_and_metrics_endpoints():
    """
    OBSERVABILITY TEST:
    Verifies /api/v1/health, /api/v1/health/live, /api/v1/health/ready, and /metrics.
    """
    # Liveness
    live_resp = client.get("/api/v1/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "alive"

    # Readiness
    ready_resp = client.get("/api/v1/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

    # Health
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["database"]["status"] == "healthy"

    # Prometheus /metrics
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "stockguard_http_requests_total" in metrics_resp.text
    assert "stockguard_outbox_backlog_total" in metrics_resp.text
