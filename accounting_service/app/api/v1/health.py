"""
Health check endpoints — liveness + readiness.
Liveness: is the process alive? (no external checks)
Readiness: are all dependencies available? (DB + Redis + Kafka)
"""
import time

import sqlalchemy
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import engine

router = APIRouter(prefix="/health", tags=["Santé"])
logger = structlog.get_logger(__name__)


@router.get("/live", summary="Liveness — process alive?")
async def liveness():
    """Returns 200 immediately. Use as Kubernetes liveness probe."""
    return {"status": "alive", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/ready", summary="Readiness — all dependencies available?")
async def readiness():
    """
    Checks PostgreSQL, Redis, and Kafka.
    Returns 200 if all healthy, 503 if any dependency is down.
    """
    checks: dict[str, dict] = {}

    # PostgreSQL
    try:
        t0 = time.monotonic()
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        logger.error("health.database_error", error=str(exc))
        checks["database"] = {"status": "error", "detail": str(exc)}

    # Redis
    try:
        from app.core.redis_pool import get_redis
        r = await get_redis()
        t0 = time.monotonic()
        await r.ping()
        checks["redis"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        logger.error("health.redis_error", error=str(exc))
        checks["redis"] = {"status": "error", "detail": str(exc)}

    # Kafka
    try:
        from aiokafka.admin import AIOKafkaAdminClient
        t0 = time.monotonic()
        admin = AIOKafkaAdminClient(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            request_timeout_ms=3000,
        )
        await admin.start()
        await admin.close()
        checks["kafka"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as exc:
        logger.error("health.kafka_error", error=str(exc))
        checks["kafka"] = {"status": "error", "detail": str(exc)}

    all_ok = all(c["status"] == "ok" for c in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ready" if all_ok else "degraded",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )
