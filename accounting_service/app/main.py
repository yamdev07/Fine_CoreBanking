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
from slowapi.util import get_remote_address

from app.api.v1 import accounts, auth, fiscal_years, journals, reports, users
from app.api.v1.journals import journals_router
from app.core.audit import AuditMiddleware
from app.core.config import settings
from app.core.exceptions import AccountingBaseError
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

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("accounting_service.starting", version=settings.APP_VERSION)

    # Seed admin par défaut
    from app.services.auth import seed_admin
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await seed_admin(session)

    # Démarrer le consommateur Kafka en arrière-plan
    from app.services.kafka_consumer import run_consumer
    from app.services.kafka_producer import stop_producer
    kafka_task = asyncio.create_task(run_consumer())

    yield

    # Arrêt propre
    kafka_task.cancel()
    try:
        await kafka_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
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


@app.get("/health", tags=["Santé"])
async def health_check():
    """Point de contrôle de santé — vérifie DB et Redis."""
    import redis.asyncio as aioredis

    from app.db.session import engine as db_engine

    checks: dict[str, str] = {}

    # Check PostgreSQL
    try:
        async with db_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"

    return {
        "status": status,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }


@app.get("/", tags=["Info"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
