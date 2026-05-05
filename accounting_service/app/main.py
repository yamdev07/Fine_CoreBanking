"""
Point d'entrée principal — Microservice Comptabilité.
"""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import accounts, auth, fiscal_years, health as health_router, journals, reports, users
from app.api.v1.journals import journals_router
from app.core.audit import AuditMiddleware
from app.core.config import settings
from app.core.exceptions import AccountingBaseError
from app.core.metrics import setup_metrics
from app.core.rate_limit import get_jwt_subject, get_user_limit
from app.db.session import AsyncSessionFactory, engine

# ─── Logging structuré ────────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

# ─── Rate limiter (partagé avec les routers via state) ───────────────────────

limiter = Limiter(key_func=get_jwt_subject, default_limits=[get_user_limit])


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("accounting_service.starting", version=settings.APP_VERSION)

    # Distributed tracing
    from app.core.telemetry import configure_tracing
    configure_tracing(app)

    # Seed admin par défaut
    from app.services.auth import seed_admin

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await seed_admin(session)

    # Démarrer le consommateur Kafka en arrière-plan
    from app.services.kafka_consumer import run_consumer, run_dlq_monitor
    from app.services.kafka_producer import stop_producer

    kafka_task = asyncio.create_task(run_consumer())
    dlq_task = asyncio.create_task(run_dlq_monitor())

    yield

    # Arrêt propre
    kafka_task.cancel()
    dlq_task.cancel()
    try:
        await kafka_task
    except asyncio.CancelledError:
        pass
    try:
        await dlq_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    from app.core.redis_pool import close_redis_pool
    await close_redis_pool()
    await engine.dispose()
    logger.info("accounting_service.stopped")


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Microservice Comptabilité",
    description="""
## Core Banking — Microservice Comptabilité

Gère le plan de comptes, les journaux, les écritures comptables
et les rapports financiers selon les normes SYSCOHADA / BCEAO.

### Règles fondamentales
- **Partie double** : ΣDébit = ΣCrédit (invariant systématique)
- **Intangibilité** : les écritures validées sont immuables
- **Clôture de période** : aucune écriture possible en période clôturée
- **Idempotence** : un événement externe → une seule écriture
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Metrics ─────────────────────────────────────────────────────────────────

setup_metrics(app)

# ─── Rate limiting ────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ─── Audit ───────────────────────────────────────────────────────────────────

app.add_middleware(AuditMiddleware)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Gestionnaires d'erreurs ──────────────────────────────────────────────────


@app.exception_handler(AccountingBaseError)
async def accounting_error_handler(request: Request, exc: AccountingBaseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "message": "Erreur interne du serveur."},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(fiscal_years.router, prefix=API_PREFIX)
app.include_router(accounts.router, prefix=API_PREFIX)
app.include_router(journals_router, prefix=API_PREFIX)
app.include_router(journals.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(health_router.router, prefix=API_PREFIX)


@app.get("/", tags=["Info"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
