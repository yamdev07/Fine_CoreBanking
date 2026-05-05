"""Prometheus metrics for reporting-service."""
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter

reporting_requests_total = Counter(
    "reporting_requests_total",
    "Total report generation requests",
    ["report_type", "format", "outcome"],
)
cache_hits_total = Counter(
    "reporting_cache_hits_total",
    "Redis cache hits for report queries",
    ["report_type"],
)
cache_misses_total = Counter(
    "reporting_cache_misses_total",
    "Redis cache misses for report queries",
    ["report_type"],
)

def setup_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[r"/health.*", "/metrics", "/"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
