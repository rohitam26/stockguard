import uuid
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient
from stockguard.database import get_session_factory
from stockguard.messaging.bus import event_bus
from stockguard.messaging.outbox_worker import OutboxWorker
from stockguard.models.outbox import OutboxMessage, OutboxStatus


def test_transactional_outbox_and_worker(client: TestClient):
    sku = f"OUTBOX-TEST-{uuid.uuid4().hex[:6].upper()}"

    # 1. Product creation generates an OutboxMessage in the same transaction
    client.post("/api/v1/products", json={
        "sku": sku,
        "name": "Outbox Verified Item",
        "price": 45.00,
        "initial_stock": 20
    })

    # Query outbox
    res = client.get("/api/v1/outbox?limit=200")
    assert res.status_code == 200
    messages = res.json()
    assert len(messages) > 0

    # Find message for this product
    prod_msg = next((m for m in messages if m["event_type"] == "product.created" and m["aggregate_id"]), None)
    assert prod_msg is not None

    # 2. Trigger Outbox Worker to process all pending messages
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        while True:
            processed = OutboxWorker.process_pending_messages(db, batch_size=200)
            if processed == 0:
                break

    # Verify message status transitioned to PUBLISHED
    res_after = client.get("/api/v1/outbox?limit=200")
    published_msg = next((m for m in res_after.json() if m["id"] == prod_msg["id"]), None)
    assert published_msg is not None
    assert published_msg["status"] == "PUBLISHED"
    assert published_msg["processed_at"] is not None


def test_consumer_idempotency_tracking(client: TestClient):
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        message_id = f"msg-{uuid.uuid4()}"
        consumer_name = "inventory_projection_worker"
        event_type = "inventory.adjusted"

        # First check: event not processed
        assert event_bus.is_event_processed(db, message_id, consumer_name) is False

        # Mark processed
        event_bus.mark_event_processed(db, message_id, consumer_name, event_type)

        # Second check: event IS processed (duplicate delivery ignored)
        assert event_bus.is_event_processed(db, message_id, consumer_name) is True


def test_event_bus_dead_letter_routing():
    failing_event_type = f"failing.event.{uuid.uuid4().hex[:6]}"
    call_attempts = [0]

    def faulty_handler(envelope):
        call_attempts[0] += 1
        raise ValueError("Simulated unrecoverable consumer error")

    event_bus.subscribe(failing_event_type, faulty_handler)

    msg_id = f"dlq-msg-{uuid.uuid4()}"
    ok = event_bus.publish(
        event_type=failing_event_type,
        payload={"data": "test"},
        message_id=msg_id,
        max_retries=3
    )

    assert ok is False, "Publish must report failure when handler retries are exhausted"
    assert call_attempts[0] == 3, "Handler must be attempted up to max_retries"

    # Verify message was routed to DLQ
    dlq_item = next((m for m in event_bus.dlq_messages if m["envelope"]["id"] == msg_id), None)
    assert dlq_item is not None
    assert dlq_item["handler"] == "faulty_handler"
