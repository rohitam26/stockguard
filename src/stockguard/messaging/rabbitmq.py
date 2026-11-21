import json
import logging
import socket
from typing import Any
import pika
from pika.exceptions import AMQPError
from stockguard.config import get_settings
from stockguard.messaging.bus import event_bus

logger = logging.getLogger("stockguard.messaging.rabbitmq")
settings = get_settings()


class RabbitMQClient:
    def __init__(self):
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None
        self._is_connected = False

    def connect(self) -> bool:
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ is disabled in configuration.")
            return False

        # Fast pre-check to avoid long socket timeout in development/test
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            # Default host and port
            sock.connect(("127.0.0.1", 5672))
            sock.close()
        except Exception:
            logger.info(
                "RabbitMQ broker not reachable on localhost:5672. Utilizing in-memory event bus."
            )
            self._is_connected = False
            return False

        try:
            params = pika.URLParameters(settings.RABBITMQ_URL)
            params.socket_timeout = 2
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            # Enable publisher confirms for guaranteed delivery
            self._channel.confirm_delivery()
            self._setup_topology()
            self._is_connected = True
            logger.info(
                "Connected to RabbitMQ with publisher confirms and declared exchange topology."
            )
            return True
        except Exception as e:
            logger.warning("RabbitMQ unavailable (%s). Falling back to in-memory event bus.", e)
            self._is_connected = False
            return False

    def _setup_topology(self):
        if not self._channel:
            return

        self._channel.exchange_declare(
            exchange=settings.RABBITMQ_EXCHANGE, exchange_type="topic", durable=True
        )

        self._channel.exchange_declare(
            exchange=settings.RABBITMQ_DLQ_EXCHANGE, exchange_type="direct", durable=True
        )

        self._channel.queue_declare(queue="stockguard.dlq.queue", durable=True)
        self._channel.queue_bind(
            queue="stockguard.dlq.queue", exchange=settings.RABBITMQ_DLQ_EXCHANGE, routing_key="dlq"
        )

        queues = {
            "stockguard.inventory": ["inventory.*", "product.*", "reservation.*"],
            "stockguard.orders": ["order.*"],
            "stockguard.payments": ["payment.*"],
            "stockguard.fulfillment": ["fulfillment.*"],
        }

        for q_name, binding_keys in queues.items():
            self._channel.queue_declare(
                queue=q_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": settings.RABBITMQ_DLQ_EXCHANGE,
                    "x-dead-letter-routing-key": "dlq",
                    "x-message-ttl": 86400000,
                },
            )
            for routing_key in binding_keys:
                self._channel.queue_bind(
                    queue=q_name, exchange=settings.RABBITMQ_EXCHANGE, routing_key=routing_key
                )

    def publish(
        self,
        routing_key: str,
        payload: dict[str, Any],
        message_id: str,
        headers: dict[str, Any] | None = None,
    ) -> bool:
        if not self._is_connected or not self._channel or self._channel.is_closed:
            return event_bus.publish(
                event_type=routing_key, payload=payload, message_id=message_id, headers=headers
            )

        try:
            properties = pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
                message_id=message_id,
                headers=headers or {},
            )
            body = json.dumps(payload, default=str)
            self._channel.basic_publish(
                exchange=settings.RABBITMQ_EXCHANGE,
                routing_key=routing_key,
                body=body.encode("utf-8"),
                properties=properties,
                mandatory=True,
            )
            return True
        except AMQPError as e:
            logger.error("Failed to publish to RabbitMQ (%s). Falling back to in-memory bus.", e)
            self._is_connected = False
            return event_bus.publish(
                event_type=routing_key, payload=payload, message_id=message_id, headers=headers
            )

    def close(self):
        """Gracefully closes channels and connections."""
        try:
            if self._channel and not self._channel.is_closed:
                self._channel.close()
            if self._connection and not self._connection.is_closed:
                self._connection.close()
            self._is_connected = False
            logger.info("RabbitMQClient connection gracefully closed.")
        except Exception as e:
            logger.warning("Error closing RabbitMQ connection: %s", e)

    @property
    def is_connected(self) -> bool:
        return self._is_connected


rabbitmq_client = RabbitMQClient()
