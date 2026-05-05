"""
Cache Invalidation Consumer — écoute accounting.events et invalide le cache Redis.

Flux :
  accounting-service  →  Kafka (accounting.events)  →  reporting-service
                                                          └─ invalide Redis

Quand une écriture est validée (ENTRY_POSTED), les rapports qui agrègent
les mouvements sont périmés. On invalide leurs clés pour forcer un recalcul
à la prochaine requête.
"""

import asyncio
import json
from datetime import UTC, datetime

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.core.config import settings
from app.utils.cache import invalidate_pattern

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
DLQ_SUFFIX = ".dlq"
DLQ_TOPIC = f"{settings.KAFKA_TOPIC_ACCOUNTING_EVENTS}{DLQ_SUFFIX}"

# Mapping event_type → patterns Redis à invalider
_INVALIDATION_MAP: dict[str, list[str]] = {
    "ENTRY_POSTED": [
        "report:trial_balance:*",
        "report:resultat:*",
        "report:dashboard:*",
        "report:credit_portfolio:*",
        "report:bilan:*",
    ],
    "FISCAL_YEAR_CLOSED": [
        "report:bilan:*",
        "report:bceao:*",
        "report:resultat:*",
        "report:dashboard:*",
    ],
}


async def _publish_dlq(
    producer: AIOKafkaProducer,
    topic: str,
    raw: dict,
    error: str,
    attempts: int,
) -> None:
    dlq_topic = f"{topic}{DLQ_SUFFIX}"
    payload = json.dumps(
        {
            "original_topic": topic,
            "original_message": raw,
            "error": error,
            "failed_at": datetime.now(UTC).isoformat(),
            "attempts": attempts,
        },
        default=str,
    ).encode()
    await producer.send_and_wait(dlq_topic, value=payload)
    logger.error(
        "kafka.dlq.published",
        topic=dlq_topic,
        event_type=raw.get("event_type"),
        error=error,
        attempts=attempts,
    )


async def run_cache_invalidation_consumer() -> None:
    """
    Consomme accounting.events et invalide les entrées Redis correspondantes.
    Retry 3x avec backoff exponentiel. Après 3 échecs : publie dans le DLQ.
    Utilise auto_offset_reset='latest' : le reporting ne rejoue pas les
    événements passés — il veut juste réagir aux nouveaux changements.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_ACCOUNTING_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"{settings.APP_NAME}-cache-invalidation",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    dlq_producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)

    await consumer.start()
    await dlq_producer.start()
    logger.info(
        "kafka.cache_invalidation_consumer.started",
        topic=settings.KAFKA_TOPIC_ACCOUNTING_EVENTS,
    )

    try:
        async for msg in consumer:
            raw = msg.value
            topic = msg.topic
            event_type = raw.get("event_type", "")

            patterns = _INVALIDATION_MAP.get(event_type)
            if not patterns:
                await consumer.commit()
                continue

            last_exc: Exception | None = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    for pattern in patterns:
                        await invalidate_pattern(pattern)
                    await consumer.commit()
                    logger.info(
                        "kafka.cache_invalidation.done",
                        event_type=event_type,
                        patterns=len(patterns),
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    wait = 2 ** attempt
                    logger.warning(
                        "kafka.cache_invalidation.retry",
                        attempt=attempt,
                        max=MAX_RETRIES,
                        event_type=event_type,
                        error=str(exc),
                        retry_in=wait,
                    )
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(wait)

            if last_exc is not None:
                await _publish_dlq(dlq_producer, topic, raw, str(last_exc), MAX_RETRIES)
                await consumer.commit()

    except asyncio.CancelledError:
        pass
    finally:
        await consumer.stop()
        await dlq_producer.stop()
        logger.info("kafka.cache_invalidation_consumer.stopped")
