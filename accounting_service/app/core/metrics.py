"""Prometheus metrics for accounting-service."""
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Gauge

journal_entries_total = Counter(
    "accounting_journal_entries_total",
    "Total journal entries created",
    ["status", "journal_code"],
)
kafka_events_processed = Counter(
    "accounting_kafka_events_total",
    "Kafka events processed",
    ["topic", "outcome"],
)
db_pool_checked_out = Gauge(
    "accounting_db_pool_checked_out",
    "Number of DB connections currently checked out",
)

def setup_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[r"/health.*", "/metrics", "/"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
