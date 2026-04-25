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
import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.utils.cache import invalidate_pattern

logger = logging.getLogger(__name__)

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


async def run_cache_invalidation_consumer() -> None:
    """
    Consomme accounting.events et invalide les entrées Redis correspondantes.
    Utilise auto_offset_reset='latest' : le reporting ne rejoue pas les
    événements passés — il veut juste réagir aux nouveaux changements.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_ACCOUNTING_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"{settings.APP_NAME}-cache-invalidation",
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda m: __import__("json").loads(m.decode("utf-8")),
    )

    await consumer.start()
    logger.info("cache_invalidation_consumer.started topic=%s",
                settings.KAFKA_TOPIC_ACCOUNTING_EVENTS)

    try:
        async for msg in consumer:
            event = msg.value
            event_type = event.get("event_type", "")
            patterns = _INVALIDATION_MAP.get(event_type)
            if not patterns:
                continue
            try:
                for pattern in patterns:
                    await invalidate_pattern(pattern)
                logger.info(
                    "cache_invalidation.done event_type=%s patterns=%d",
                    event_type, len(patterns),
                )
            except Exception as exc:
                logger.error("cache_invalidation.failed event_type=%s error=%s",
                             event_type, exc)
    except asyncio.CancelledError:
        pass
    finally:
        await consumer.stop()
        logger.info("cache_invalidation_consumer.stopped")
