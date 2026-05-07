"""
Tests unitaires — Service Comptabilité.
Utilise pytest-asyncio + SQLite en mémoire pour l'isolation complète.

Couverture :
  - AccountService   : création, hiérarchie, solde, désactivation
  - FiscalYearService: création avec périodes, clôture
  - JournalEntryService: partie double, intangibilité, extourne, idempotence
  - LetteringService : lettrage équilibré, erreurs
  - ReportService    : balance, grand livre
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import (
    AccountAlreadyExistsError,
    AccountHasBalanceError,
    AccountHasChildrenError,
    FiscalYearClosedError,
    JournalEntryAlreadyPostedError,
    JournalEntryAlreadyReversedError,
    PeriodClosedError,
    PeriodNotFoundError,
)
from app.models.accounting import (
    AccountClass,
    AccountingPeriod,
    AccountNature,
    AccountPlan,
    AccountType,
    Base,
    EntryStatus,
    FiscalYear,
    FiscalYearStatus,
    Journal,
    JournalCode,
    JournalLine,
    PeriodStatus,
)
from app.schemas.accounting import (
    AccountCreate,
    FiscalYearCreate,
    JournalEntryCreate,
    JournalLineCreate,
)
from app.services.accounting import (
    AccountService,
    FiscalYearService,
    JournalEntryService,
    ReportService,
)

# ─── Session fixture (SQLite per test) ───────────────────────────────────────


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess

    await engine.dispose()


# ─── Common fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def fiscal_year(session):
    fy = FiscalYear(
        id=str(uuid.uuid4()),
        name="2024",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    session.add(fy)
    await session.flush()
    return fy


@pytest_asyncio.fixture
async def open_period(session, fiscal_year):
    period = AccountingPeriod(
        id=str(uuid.uuid4()),
        fiscal_year_id=fiscal_year.id,
        name="2024-01",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        status=PeriodStatus.OPEN,
    )
    session.add(period)
    await session.flush()
    return period


@pytest_asyncio.fixture
async def cash_account(session):
    acc = AccountPlan(
        id=str(uuid.uuid4()),
        code="571100",
        name="Caisse principale",
        account_class=AccountClass.TRESORERIE,
        account_type=AccountType.ACTIF,
        account_nature=AccountNature.DEBITEUR,
        currency="XOF",
    )
    session.add(acc)
    await session.flush()
    return acc


@pytest_asyncio.fixture
async def credit_account(session):
    acc = AccountPlan(
        id=str(uuid.uuid4()),
        code="251100",
        name="Crédits court terme",
        account_class=AccountClass.TIERS,
        account_type=AccountType.ACTIF,
        account_nature=AccountNature.DEBITEUR,
        currency="XOF",
    )
    session.add(acc)
    await session.flush()
    return acc


@pytest_asyncio.fixture
async def journal_caisse(session):
    j = Journal(
        id=str(uuid.uuid4()),
        code="CJ",
        name="Journal Caisse",
        journal_type=JournalCode.CJ,
        sequence_prefix="CJ-",
        last_sequence=0,
    )
    session.add(j)
    await session.flush()
    return j


@pytest_asyncio.fixture
async def journal_extourne(session):
    j = Journal(
        id=str(uuid.uuid4()),
        code="EX",
        name="Extournes",
        journal_type=JournalCode.EX,
        sequence_prefix="EX-",
        last_sequence=0,
    )
    session.add(j)
    await session.flush()
    return j


# ─── AccountService ───────────────────────────────────────────────────────────


class TestAccountService:
    async def test_create_account_success(self, session):
        svc = AccountService(session)
        account = await svc.create(
            AccountCreate(
                code="411000",
                name="Clients",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
            )
        )
        assert account.code == "411000"
        assert account.is_leaf is True
        assert account.level == 1

    async def test_create_duplicate_code_raises(self, session):
        svc = AccountService(session)
        data = AccountCreate(
            code="411000",
            name="Clients",
            account_class=AccountClass.TIERS,
            account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR,
        )
        await svc.create(data)
        with pytest.raises(AccountAlreadyExistsError):
            await svc.create(data)

    async def test_parent_becomes_non_leaf(self, session):
        svc = AccountService(session)
        parent = await svc.create(
            AccountCreate(
                code="41",
                name="Clients (parent)",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
            )
        )
        assert parent.is_leaf is True

        await svc.create(
            AccountCreate(
                code="411000",
                name="Clients courants",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
                parent_id=parent.id,
            )
        )
        refreshed = await session.get(AccountPlan, parent.id)
        assert refreshed.is_leaf is False

    async def test_child_inherits_hierarchy(self, session):
        svc = AccountService(session)
        parent = await svc.create(
            AccountCreate(
                code="41",
                name="Clients",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
            )
        )
        child = await svc.create(
            AccountCreate(
                code="411000",
                name="Clients courants",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
                parent_id=parent.id,
            )
        )
        assert child.level == 2
        assert parent.id in child.path

    async def test_deactivate_account_with_children_raises(self, session):
        svc = AccountService(session)
        parent = await svc.create(
            AccountCreate(
                code="41",
                name="Parent",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
            )
        )
        await svc.create(
            AccountCreate(
                code="411000",
                name="Child",
                account_class=AccountClass.TIERS,
                account_type=AccountType.ACTIF,
                account_nature=AccountNature.DEBITEUR,
                parent_id=parent.id,
            )
        )
        with pytest.raises(AccountHasChildrenError):
            await svc.deactivate(parent.id)

    async def test_deactivate_account_with_balance_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        entry_svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Mouvement sur compte",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("100000")),
            ],
        )
        entry = await entry_svc.create_entry(data, created_by="test")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await entry_svc.post_entry(entry.id, posted_by="test")

        account_svc = AccountService(session)
        with pytest.raises(AccountHasBalanceError):
            await account_svc.deactivate(cash_account.id)

    async def test_deactivate_account_no_balance_succeeds(self, session):
        svc = AccountService(session)
        acc = await svc.create(
            AccountCreate(
                code="900000",
                name="Compte vide",
                account_class=AccountClass.CHARGES,
                account_type=AccountType.CHARGE,
                account_nature=AccountNature.DEBITEUR,
            )
        )
        result = await svc.deactivate(acc.id)
        assert result.is_active is False

    async def test_account_balance_debit_nature(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 15),
            description="Test solde",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("500000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("500000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="test")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="test")

        balance = await AccountService(session).get_balance(
            credit_account.id, date(2024, 1, 1), date(2024, 1, 31)
        )
        assert balance["balance"] == Decimal("500000")
        assert balance["balance_nature"] == "DEBITEUR"


# ─── FiscalYearService ────────────────────────────────────────────────────────


class TestFiscalYearService:
    async def test_create_generates_12_periods(self, session):
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            svc = FiscalYearService(session)
            fy = await svc.create(
                FiscalYearCreate(
                    name="2025",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 12, 31),
                )
            )
            periods = await svc.period_repo.list_by_fiscal_year(fy.id)
        assert len(periods) == 12
        assert periods[0].name == "2025-01"
        assert periods[11].name == "2025-12"

    async def test_create_short_year_generates_correct_periods(self, session):
        svc = FiscalYearService(session)
        fy = await svc.create(
            FiscalYearCreate(
                name="2025-Q1",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 31),
            )
        )
        periods = await svc.period_repo.list_by_fiscal_year(fy.id)
        assert len(periods) == 3

    async def test_close_fiscal_year_sets_status_closed(self, session, fiscal_year, open_period):
        svc = FiscalYearService(session)
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            closed = await svc.close(fiscal_year.id, closed_by="admin-001")
        assert closed.status == FiscalYearStatus.CLOSED
        assert closed.closed_by == "admin-001"
        assert closed.closed_at is not None

    async def test_close_fiscal_year_locks_all_periods(self, session, fiscal_year, open_period):
        svc = FiscalYearService(session)
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.close(fiscal_year.id, closed_by="admin-001")
        from sqlalchemy import select

        from app.models.accounting import AccountingPeriod

        result = await session.execute(
            select(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fiscal_year.id)
        )
        for p in result.scalars().all():
            assert p.status == PeriodStatus.LOCKED

    async def test_close_already_closed_fiscal_year_raises(self, session, fiscal_year, open_period):
        svc = FiscalYearService(session)
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.close(fiscal_year.id, closed_by="admin-001")
            with pytest.raises(FiscalYearClosedError):
                await svc.close(fiscal_year.id, closed_by="admin-001")

    async def test_list_all_returns_fiscal_years(self, session, fiscal_year):
        svc = FiscalYearService(session)
        result = await svc.list_all()
        assert any(fy.id == fiscal_year.id for fy in result)


# ─── JournalEntryService — Partie double ─────────────────────────────────────


class TestDoubleEntry:
    async def test_balanced_entry_accepted(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Test",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("1000000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("1000000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user-1")
        assert entry.total_debit == Decimal("1000000")
        assert entry.total_credit == Decimal("1000000")
        assert entry.status == EntryStatus.DRAFT

    async def test_imbalanced_entry_rejected_by_schema(
        self, session, cash_account, credit_account, journal_caisse
    ):
        with pytest.raises(Exception) as exc_info:
            JournalEntryCreate(
                journal_id=journal_caisse.id,
                entry_date=date(2024, 1, 10),
                description="Déséquilibré",
                lines=[
                    JournalLineCreate(
                        account_id=credit_account.id, debit_amount=Decimal("1000000")
                    ),
                    JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("900000")),
                ],
            )
        assert (
            "déséquilibr" in str(exc_info.value).lower()
            or "imbalanced" in str(exc_info.value).lower()
        )

    async def test_line_cannot_have_both_debit_and_credit(self, session):
        with pytest.raises(Exception):
            JournalLineCreate(
                account_id=str(uuid.uuid4()),
                debit_amount=Decimal("100"),
                credit_amount=Decimal("100"),
            )

    async def test_line_must_have_nonzero_amount(self, session):
        with pytest.raises(Exception):
            JournalLineCreate(account_id=str(uuid.uuid4()))

    async def test_entry_number_is_sequential(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        base = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Test",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100000")),
            ],
        )
        e1 = await svc.create_entry(base, created_by="u1")
        e2 = await svc.create_entry(base, created_by="u1")
        assert e1.entry_number != e2.entry_number
        assert e1.entry_number < e2.entry_number

    async def test_create_entry_no_open_period_raises(
        self, session, cash_account, credit_account, journal_caisse
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2020, 6, 15),  # No period for this date
            description="Pas de période",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100")),
            ],
        )
        with pytest.raises(PeriodNotFoundError):
            await svc.create_entry(data, created_by="user")

    async def test_create_entry_inactive_account_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        # Deactivate credit account
        credit_account.is_active = False
        await session.flush()

        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Compte inactif",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100000")),
            ],
        )
        from app.core.exceptions import AccountNotActiveError

        with pytest.raises(AccountNotActiveError):
            await svc.create_entry(data, created_by="user")

    async def test_create_entry_in_closed_fiscal_year_raises(
        self, session, cash_account, credit_account, journal_caisse, fiscal_year, open_period
    ):
        fiscal_year.status = FiscalYearStatus.CLOSED
        await session.flush()

        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Exercice clôturé",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100000")),
            ],
        )
        with pytest.raises(FiscalYearClosedError):
            await svc.create_entry(data, created_by="user")


# ─── JournalEntryService — Validation / Intangibilité ────────────────────────


class TestPostEntry:
    async def test_post_changes_status_to_posted(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 5),
            description="Remboursement",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("200000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("200000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        assert entry.status == EntryStatus.DRAFT

        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            posted = await svc.post_entry(entry.id, posted_by="supervisor")
        assert posted.status == EntryStatus.POSTED
        assert posted.posted_by == "supervisor"

    async def test_post_twice_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 5),
            description="Test",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("50000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("50000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="supervisor")
            with pytest.raises(JournalEntryAlreadyPostedError):
                await svc.post_entry(entry.id, posted_by="supervisor")

    async def test_post_on_closed_period_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 5),
            description="Période fermée",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("75000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("75000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        open_period.status = PeriodStatus.CLOSED
        await session.flush()

        with pytest.raises(PeriodClosedError):
            await svc.post_entry(entry.id, posted_by="supervisor")


# ─── JournalEntryService — Extourne ──────────────────────────────────────────


class TestReverseEntry:
    async def test_reversal_inverts_debit_credit(
        self, session, cash_account, credit_account, journal_caisse, journal_extourne, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Décaissement à extourner",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("300000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("300000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="supervisor")
            reversal = await svc.reverse_entry(
                entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15)
            )

        assert reversal.status == EntryStatus.POSTED
        assert reversal.total_debit == Decimal("300000")
        assert reversal.total_credit == Decimal("300000")

        from sqlalchemy import select

        lines = list(
            (
                await session.execute(
                    select(JournalLine)
                    .where(JournalLine.entry_id == reversal.id)
                    .order_by(JournalLine.line_number)
                )
            )
            .scalars()
            .all()
        )
        assert lines[0].credit_amount == Decimal("300000")
        assert lines[0].debit_amount == Decimal("0")
        assert lines[1].debit_amount == Decimal("300000")
        assert lines[1].credit_amount == Decimal("0")

    async def test_original_marked_reversed(
        self, session, cash_account, credit_account, journal_caisse, journal_extourne, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Original",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("150000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("150000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="supervisor")
            await svc.reverse_entry(
                entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15)
            )

        refreshed = await session.get(type(entry), entry.id)
        assert refreshed.status == EntryStatus.REVERSED

    async def test_reverse_draft_entry_raises(
        self, session, cash_account, credit_account, journal_caisse, journal_extourne, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Brouillon",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with pytest.raises(JournalEntryAlreadyReversedError):
            await svc.reverse_entry(
                entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15)
            )

    async def test_reverse_already_reversed_raises(
        self, session, cash_account, credit_account, journal_caisse, journal_extourne, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="À extourner deux fois",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("200000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("200000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="supervisor")
            await svc.reverse_entry(
                entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15)
            )
            with pytest.raises(JournalEntryAlreadyReversedError):
                await svc.reverse_entry(
                    entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 20)
                )

    async def test_reverse_no_open_period_raises(
        self, session, cash_account, credit_account, journal_caisse, journal_extourne, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Test",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await svc.post_entry(entry.id, posted_by="supervisor")
        # Reversal date with no open period
        with pytest.raises(PeriodNotFoundError):
            await svc.reverse_entry(
                entry.id, reversed_by="supervisor", reversal_date=date(2025, 6, 1)
            )


# ─── Idempotence ──────────────────────────────────────────────────────────────


class TestIdempotence:
    async def test_same_event_id_returns_existing_entry(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 20),
            description="Idempotent",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("50000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("50000")),
            ],
        )
        e1 = await svc.create_entry(
            data, created_by="kafka", source_service="credit", source_event_id="evt-001"
        )
        e2 = await svc.create_entry(
            data, created_by="kafka", source_service="credit", source_event_id="evt-001"
        )
        assert e1.id == e2.id

    async def test_different_event_ids_create_separate_entries(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 20),
            description="Événements distincts",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("10000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("10000")),
            ],
        )
        e1 = await svc.create_entry(
            data, created_by="kafka", source_service="credit", source_event_id="evt-001"
        )
        e2 = await svc.create_entry(
            data, created_by="kafka", source_service="credit", source_event_id="evt-002"
        )
        assert e1.id != e2.id


# ─── Lettrage ─────────────────────────────────────────────────────────────────


class TestLettering:
    async def _create_posted_entry(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 15),
            description="À lettrer",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("200000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("200000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            entry = await svc.post_entry(entry.id, posted_by="supervisor")
        return await svc.entry_repo.get_by_id(entry.id, with_lines=True)

    async def test_balanced_lettering_success(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        entry = await self._create_posted_entry(
            session, cash_account, credit_account, journal_caisse, open_period
        )
        line_ids = [ln.id for ln in entry.lines]

        svc = JournalEntryService(session)
        result = await svc.letter_lines(line_ids, lettered_by="supervisor")
        assert result["lettered_lines"] == 2
        assert result["is_balanced"] is True
        assert result["lettering_code"] is not None

    async def test_already_lettered_lines_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        from app.core.exceptions import LineAlreadyLetteredError

        entry = await self._create_posted_entry(
            session, cash_account, credit_account, journal_caisse, open_period
        )
        line_ids = [ln.id for ln in entry.lines]

        svc = JournalEntryService(session)
        await svc.letter_lines(line_ids, lettered_by="supervisor")
        with pytest.raises(LineAlreadyLetteredError):
            await svc.letter_lines(line_ids, lettered_by="supervisor")

    async def test_imbalanced_lettering_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        from app.core.exceptions import LetteringImbalancedError

        entry = await self._create_posted_entry(
            session, cash_account, credit_account, journal_caisse, open_period
        )
        # Only one line (debit without matching credit)
        debit_only = [ln.id for ln in entry.lines if ln.debit_amount > 0]

        svc = JournalEntryService(session)
        with pytest.raises(LetteringImbalancedError):
            await svc.letter_lines(debit_only, lettered_by="supervisor")


# ─── ReportService ────────────────────────────────────────────────────────────


class TestReportService:
    async def test_trial_balance_empty_returns_balanced(self, session, cash_account):
        svc = ReportService(session)
        result = await svc.trial_balance(date(2024, 1, 1), date(2024, 1, 31))
        assert result["is_balanced"] is True
        assert result["total_debit"] == Decimal("0")
        assert result["total_credit"] == Decimal("0")
        assert result["lines"] == []

    async def test_trial_balance_with_posted_entry(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        entry_svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 15),
            description="Pour balance",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("750000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("750000")),
            ],
        )
        entry = await entry_svc.create_entry(data, created_by="test")
        with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
            await entry_svc.post_entry(entry.id, posted_by="test")

        svc = ReportService(session)
        result = await svc.trial_balance(date(2024, 1, 1), date(2024, 1, 31))
        assert result["is_balanced"] is True
        assert result["total_debit"] == Decimal("750000")
        assert result["total_credit"] == Decimal("750000")
        assert len(result["lines"]) == 2

    async def test_draft_entry_excluded_from_trial_balance(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        entry_svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 15),
            description="Brouillon",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("100000")),
            ],
        )
        await entry_svc.create_entry(data, created_by="test")  # NOT posted

        svc = ReportService(session)
        result = await svc.trial_balance(date(2024, 1, 1), date(2024, 1, 31))
        assert result["total_debit"] == Decimal("0")

    async def test_general_ledger_running_balance_progression(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        entry_svc = JournalEntryService(session)
        amounts = [Decimal("100000"), Decimal("200000"), Decimal("50000")]
        for amount in amounts:
            data = JournalEntryCreate(
                journal_id=journal_caisse.id,
                entry_date=date(2024, 1, 15),
                description=f"Mouvement {amount}",
                lines=[
                    JournalLineCreate(account_id=cash_account.id, debit_amount=amount),
                    JournalLineCreate(account_id=credit_account.id, credit_amount=amount),
                ],
            )
            entry = await entry_svc.create_entry(data, created_by="test")
            with patch("app.services.kafka_producer._publish", new_callable=AsyncMock):
                await entry_svc.post_entry(entry.id, posted_by="test")

        svc = ReportService(session)
        result = await svc.general_ledger(cash_account.id, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result["lines"]) == 3
        assert result["total_debit"] == sum(amounts)
        # Solde progressif croissant pour un compte débiteur
        balances = [ln["running_balance"] for ln in result["lines"]]
        assert balances[0] < balances[1] < balances[2]  # 100k, 300k, 350k
