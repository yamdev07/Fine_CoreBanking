"""
Point d'entrée — Microservice Reporting.
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

from app.api.v1 import health as health_router, reports
from app.core.config import settings
from app.core.exceptions import ReportingBaseError
from app.core.metrics import setup_metrics
from app.core.rate_limit import get_jwt_subject, get_user_limit
from app.db.session import engine

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


limiter = Limiter(key_func=get_jwt_subject, default_limits=[get_user_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("reporting_service.starting", version=settings.APP_VERSION)

    # Distributed tracing
    from app.core.telemetry import configure_tracing
    configure_tracing(app)

    from app.services.kafka_consumer import run_cache_invalidation_consumer

    kafka_task = asyncio.create_task(run_cache_invalidation_consumer())

    yield

    kafka_task.cancel()
    try:
        await kafka_task
    except asyncio.CancelledError:
        pass
    from app.core.redis_pool import close_redis_pool
    await close_redis_pool()
    await engine.dispose()
    logger.info("reporting_service.stopped")


app = FastAPI(
    title="Microservice Reporting",
    description="""
## Core Banking — Microservice Reporting

Génère tous les rapports financiers et réglementaires du core banking.
Connexion en **lecture seule** sur la base comptabilité.

### Rapports disponibles
| Endpoint | Description |
|---|---|
| `GET /reports/trial-balance` | Balance générale |
| `GET /reports/general-ledger` | Grand livre d'un compte |
| `GET /reports/balance-sheet` | Bilan comptable (Actif/Passif) |
| `GET /reports/income-statement` | Compte de résultat |
| `GET /reports/cash-flow` | Flux de trésorerie |
| `GET /reports/credit-portfolio` | Portefeuille crédits & impayés |
| `GET /reports/deposits` | État des dépôts & épargne |
| `GET /reports/dashboard` | Tableau de bord KPIs |
| `GET /reports/bceao-prudential` | Ratios prudentiels BCEAO/UEMOA |
| `GET /reports/journal-centralizer` | Journal centralisateur |

### Formats d'export
Tous les endpoints acceptent `?format=json|pdf|excel`
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

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],  # Lecture seule — aucun POST/PUT/DELETE
    allow_headers=["*"],
)

# SlowAPIMiddleware added last so Starlette applies it first (outermost layer)
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(ReportingBaseError)
async def reporting_error_handler(request: Request, exc: ReportingBaseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "message": "Erreur interne."},
    )


app.include_router(reports.router, prefix="/api/v1")
app.include_router(health_router.router, prefix="/api/v1")


@app.get("/", tags=["Info"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "reports": 10,
        "docs": "/docs",
    }
