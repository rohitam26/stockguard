import json
import logging
import threading
from typing import Callable, Any
import pika
from stockguard.config import get_settings
from stockguard.database import get_session_factory
from stockguard.models.event import ProcessedEvent

logger = logging.getLogger("stockguard.messaging.consumer")
settings = get_settings()


class RabbitMQConsumerWorker:
    """
    Production-grade AMQP Consumer Worker for RabbitMQ.
    Features:
    - Durable queue subscription.
    - Manual message acknowledgements (basic_ack / basic_nack).
    - Idempotent consumer deduplication via PostgreSQL processed_events table.
    - Dead-letter queue routing on error (basic_nack with requeue=False).
    - Graceful startup and shutdown.
    """

    def __init__(
        self,
        queue_name: str,
        consumer_name: str | None = None,
        handler: Callable[[str, dict[str, Any], dict[str, Any]], bool] | None = None,
    ):
        self.queue_name = queue_name
        self.consumer_name = consumer_name or f"{queue_name}.worker"
        self.handler = handler or self._default_handler
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None
        self._is_running = False
        self._thread: threading.Thread | None = None

    def connect(self) -> bool:
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ is disabled in settings.")
            return False

        try:
            params = pika.URLParameters(settings.RABBITMQ_URL)
            params.socket_timeout = 2
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            # Set prefetch count for fair dispatch
            self._channel.basic_qos(prefetch_count=10)
            logger.info("RabbitMQConsumerWorker connected to %s", self.queue_name)
            return True
        except Exception as e:
            logger.warning("RabbitMQConsumerWorker could not connect (%s)", e)
            return False

    def _default_handler(
        self, routing_key: str, payload: dict[str, Any], headers: dict[str, Any]
    ) -> bool:
        logger.info(
            "[%s] Received event '%s': %s",
            self.consumer_name,
            routing_key,
            json.dumps(payload, default=str)[:200],
        )
        return True

    def process_delivery(
        self,
        ch: pika.adapters.blocking_connection.BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ):
        message_id = properties.message_id or (properties.headers or {}).get("message_id")
        if not message_id:
            message_id = f"anon-{method.delivery_tag}"

        event_key = f"{message_id}:{self.consumer_name}"
        SessionFactory = get_session_factory()

        # 1. Idempotency Check in Database
        with SessionFactory() as db:
            existing = db.get(ProcessedEvent, event_key)
            if existing:
                logger.info(
                    "[%s] Event %s already processed. Acknowledging duplicate.",
                    self.consumer_name,
                    event_key,
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

        # 2. Decode payload
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.error(
                "[%s] Malformed JSON payload (%s). Rejecting to DLQ.", self.consumer_name, e
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        # 3. Execute Handler
        headers = properties.headers or {}
        try:
            success = self.handler(method.routing_key, payload, headers)
            if success:
                # 4. Record Idempotency Tracking & Ack
                with SessionFactory() as db:
                    processed_record = ProcessedEvent(
                        id=event_key,
                        consumer_name=self.consumer_name,
                        event_type=method.routing_key,
                    )
                    db.add(processed_record)
                    db.commit()

                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug(
                    "[%s] Successfully processed & acknowledged event %s",
                    self.consumer_name,
                    message_id,
                )
            else:
                raise RuntimeError("Handler returned failure status")
        except Exception as e:
            logger.error(
                "[%s] Error processing event %s (%s). Routing to Dead-Letter Queue.",
                self.consumer_name,
                message_id,
                e,
            )
            # Requeue=False routes to x-dead-letter-exchange (stockguard.dlq)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        if not self._channel or self._channel.is_closed:
            if not self.connect():
                raise ConnectionError("Unable to connect to RabbitMQ broker")

        self._is_running = True
        self._channel.basic_consume(
            queue=self.queue_name, on_message_callback=self.process_delivery, auto_ack=False
        )
        logger.info("[%s] Started consuming from %s...", self.consumer_name, self.queue_name)
        try:
            self._channel.start_consuming()
        except Exception as e:
            logger.info("[%s] Consumer loop stopped (%s)", self.consumer_name, e)
        finally:
            self._is_running = False

    def start_in_thread(self) -> threading.Thread:
        self._thread = threading.Thread(
            target=self.start_consuming, name=f"ConsumerThread-{self.queue_name}", daemon=True
        )
        self._thread.start()
        return self._thread

    def stop(self):
        self._is_running = False
        if self._channel and self._channel.is_open:
            try:
                self._channel.stop_consuming()
                self._channel.close()
            except Exception:
                pass
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass
        logger.info("[%s] Consumer stopped.", self.consumer_name)
