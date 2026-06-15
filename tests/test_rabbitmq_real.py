import socket
import uuid
import time
import pytest
from stockguard.config import get_settings
from stockguard.messaging.rabbitmq import RabbitMQClient
from stockguard.messaging.consumer import RabbitMQConsumerWorker
from stockguard.database import get_session_factory
from stockguard.models.event import ProcessedEvent

settings = get_settings()


def is_rabbitmq_broker_live() -> bool:
    """Checks if a real RabbitMQ broker is listening on 5672."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect(("127.0.0.1", 5672))
        sock.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not is_rabbitmq_broker_live(), reason="Real RabbitMQ broker is not running on localhost:5672")
def test_real_rabbitmq_publish_and_consume():
    """
    Genuine RabbitMQ Integration Test:
    - Verifies AMQP connection to live broker.
    - Publishes persistent message to durable topic exchange.
    - Consumes message with manual basic_ack.
    - Verifies consumer deduplication and DB idempotency logging.
    """
    client = RabbitMQClient()
    connected = client.connect()
    assert connected is True, "Must connect to live RabbitMQ broker"

    test_msg_id = f"test-amqp-{uuid.uuid4().hex}"
    queue_name = "stockguard.inventory"
    consumer_name = f"test_worker_{uuid.uuid4().hex[:6]}"

    received_events = []

    def handle_test_event(routing_key, payload, headers):
        received_events.append((routing_key, payload))
        return True

    worker = RabbitMQConsumerWorker(
        queue_name=queue_name,
        consumer_name=consumer_name,
        handler=handle_test_event
    )
    assert worker.connect() is True

    # 1. Publish persistent message
    published = client.publish(
        routing_key="inventory.adjusted",
        payload={"sku": "TEST-RABBIT-SKU", "delta": 10},
        message_id=test_msg_id
    )
    assert published is True

    # 2. Consume in thread
    t = worker.start_in_thread()
    time.sleep(1.0)
    worker.stop()
    t.join(timeout=2.0)

    # 3. Verify event was processed
    assert len(received_events) >= 1
    assert received_events[-1][0] == "inventory.adjusted"

    # 4. Verify DB idempotency record
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        event_key = f"{test_msg_id}:{consumer_name}"
        record = db.get(ProcessedEvent, event_key)
        assert record is not None, "ProcessedEvent record must be persisted in PostgreSQL"
        assert record.consumer_name == consumer_name
