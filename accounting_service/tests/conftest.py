"""
Shared test fixtures — unit tests and API integration tests.
"""
import os
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models.accounting import (
    AccountClass, AccountNature, AccountPlan, AccountType,
    AccountingPeriod, Base, FiscalYear, Journal, JournalCode,
    JournalEntry, JournalLine, PeriodStatus,
)
from app.models.auth import User, UserRole
from app.services.auth import hash_password

# ─── Fixed test IDs (deterministic across fixtures) ──────────────────────────

ADMIN_ID       = "10000000-0000-0000-0000-000000000001"
ACCOUNTANT_ID  = "10000000-0000-0000-0000-000000000002"
AUDITOR_ID     = "10000000-0000-0000-0000-000000000003"

CAISSE_JOURNAL_ID   = "20000000-0000-0000-0000-000000000001"
EXTOURNE_JOURNAL_ID = "20000000-0000-0000-0000-000000000002"

CASH_ACCOUNT_ID   = "30000000-0000-0000-0000-000000000001"
CREDIT_ACCOUNT_ID = "30000000-0000-0000-0000-000000000002"

FISCAL_YEAR_ID = "40000000-0000-0000-0000-000000000001"
PERIOD_ID      = "50000000-0000-0000-0000-000000000001"


# ─── SQLite engine (file-based per test for guaranteed isolation) ─────────────

@pytest_asyncio.fixture
async def engine():
    """Isolated SQLite DB per test function — file-based to avoid aiosqlite
    thread/event-loop issues that affect in-memory StaticPool across tests."""
    db_path = f"/tmp/testdb_{uuid.uuid4().hex}.db"
    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Session for direct service/repository tests."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def make_token(user_id: str, role: str, expired: bool = False) -> str:
    delta = -3600 if expired else 3600
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=delta)).timestamp())
    return jwt.encode(
        {"sub": user_id, "roles": [role], "exp": exp},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest.fixture
def admin_headers() -> dict:
    return {"Authorization": f"Bearer {make_token(ADMIN_ID, 'ADMIN')}"}


@pytest.fixture
def accountant_headers() -> dict:
    return {"Authorization": f"Bearer {make_token(ACCOUNTANT_ID, 'ACCOUNTANT')}"}


@pytest.fixture
def auditor_headers() -> dict:
    return {"Authorization": f"Bearer {make_token(AUDITOR_ID, 'AUDITOR')}"}


@pytest.fixture
def expired_token_headers() -> dict:
    return {"Authorization": f"Bearer {make_token(ADMIN_ID, 'ADMIN', expired=True)}"}


# ─── Seed helpers ─────────────────────────────────────────────────────────────

async def seed_base_data(session: AsyncSession) -> None:
    """Insert minimum data required by API tests (idempotent)."""
    # Clear in FK-safe reverse order before re-seeding
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(delete(table))

    session.add_all([
        User(
            id=ADMIN_ID, username="admin", full_name="Admin Test",
            email="admin@test.local", hashed_password=hash_password("Admin1234!"),
            role=UserRole.ADMIN, is_active=True,
        ),
        User(
            id=ACCOUNTANT_ID, username="accountant", full_name="Accountant Test",
            email="accountant@test.local", hashed_password=hash_password("Acc1234!"),
            role=UserRole.ACCOUNTANT, is_active=True,
        ),
        User(
            id=AUDITOR_ID, username="auditor", full_name="Auditor Test",
            email="auditor@test.local", hashed_password=hash_password("Aud1234!"),
            role=UserRole.AUDITOR, is_active=True,
        ),
        Journal(
            id=CAISSE_JOURNAL_ID, code="CJ", name="Journal Caisse",
            journal_type=JournalCode.CJ, sequence_prefix="CJ-", last_sequence=0,
        ),
        Journal(
            id=EXTOURNE_JOURNAL_ID, code="EX", name="Extournes",
            journal_type=JournalCode.EX, sequence_prefix="EX-", last_sequence=0,
        ),
        AccountPlan(
            id=CASH_ACCOUNT_ID, code="571100", name="Caisse principale",
            account_class=AccountClass.TRESORERIE, account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR, currency="XOF",
        ),
        AccountPlan(
            id=CREDIT_ACCOUNT_ID, code="251100", name="Crédits court terme",
            account_class=AccountClass.TIERS, account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR, currency="XOF",
        ),
        FiscalYear(
            id=FISCAL_YEAR_ID, name="2024",
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        ),
        AccountingPeriod(
            id=PERIOD_ID, fiscal_year_id=FISCAL_YEAR_ID, name="2024-01",
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31),
            status=PeriodStatus.OPEN,
        ),
    ])
    await session.flush()


# ─── API Client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def api_client(engine):
    """
    Full integration test client:
    - SQLite in-memory DB (fresh per test)
    - Seeded with users, journals, accounts, fiscal year, period
    - Kafka and seed_admin patched out
    """
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Commit seed data so all subsequent sessions see it
    async with factory() as sess:
        async with sess.begin():
            await seed_base_data(sess)

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as sess:
            async with sess.begin():
                try:
                    yield sess
                except Exception:
                    await sess.rollback()
                    raise

    app.dependency_overrides[get_session] = _override_session

    try:
        with (
            patch("app.services.auth.seed_admin", new_callable=AsyncMock),
            patch("app.services.kafka_consumer.run_consumer", new_callable=AsyncMock),
            patch("app.services.kafka_producer._publish", new_callable=AsyncMock),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
