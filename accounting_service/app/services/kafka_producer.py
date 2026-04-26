"""
Kafka Producer — Publie les événements comptables vers accounting.events.
Les autres microservices (reporting, etc.) consomment ce topic.
"""
import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            acks="all",           # Durabilité garantie
            retry_backoff_ms=200,
        )
        await _producer.start()
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


async def _publish(event: dict) -> None:
    """Publication best-effort — ne bloque pas si Kafka est indisponible."""
    try:
        producer = await get_producer()
        await producer.send_and_wait(settings.KAFKA_TOPIC_ACCOUNTING_EVENTS, value=event)
    except Exception as exc:
        logger.error("kafka_producer.publish_failed event_type=%s error=%s",
                     event.get("event_type"), exc)


async def publish_entry_posted(
    entry_id: str,
    entry_number: str,
    entry_date: str,
    total_debit: str,
    total_credit: str,
) -> None:
    await _publish({
        "event_type": "ENTRY_POSTED",
        "source_service": "accounting-service",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "entry_id": entry_id,
            "entry_number": entry_number,
            "entry_date": entry_date,
            "total_debit": total_debit,
            "total_credit": total_credit,
        },
    })
    logger.info("kafka_producer.entry_posted entry_number=%s", entry_number)


async def publish_fiscal_year_closed(
    fiscal_year_id: str,
    fiscal_year_name: str,
) -> None:
    await _publish({
        "event_type": "FISCAL_YEAR_CLOSED",
        "source_service": "accounting-service",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "fiscal_year_id": fiscal_year_id,
            "fiscal_year_name": fiscal_year_name,
        },
    })
    logger.info("kafka_producer.fiscal_year_closed name=%s", fiscal_year_name)
