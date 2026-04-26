"""
Tests unitaires — Service Comptabilité.
Utilise pytest-asyncio + SQLite en mémoire pour l'isolation.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import (
    AccountAlreadyExistsError, JournalEntryImbalancedError,
    JournalEntryAlreadyPostedError, PeriodClosedError,
)
from app.models.accounting import (
    AccountClass, AccountNature, AccountPlan, AccountType,
    AccountingPeriod, EntryStatus, FiscalYear, Journal, JournalCode,
    PeriodStatus, Base,
)
from app.repositories.accounting import (
    AccountRepository, FiscalYearRepository, JournalRepository,
    PeriodRepository,
)
from app.schemas.accounting import (
    AccountCreate, FiscalYearCreate, JournalEntryCreate, JournalLineCreate,
)
from app.services.accounting import (
    AccountService, FiscalYearService, JournalEntryService,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def session():
    """Session SQLite en mémoire — isolée par test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess

    await engine.dispose()


@pytest_asyncio.fixture
async def fiscal_year(session: AsyncSession) -> FiscalYear:
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
async def open_period(session: AsyncSession, fiscal_year: FiscalYear) -> AccountingPeriod:
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
async def cash_account(session: AsyncSession) -> AccountPlan:
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
async def credit_account(session: AsyncSession) -> AccountPlan:
    acc = AccountPlan(
        id=str(uuid.uuid4()),
        code="251100",
        name="Crédits à court terme",
        account_class=AccountClass.TIERS,
        account_type=AccountType.ACTIF,
        account_nature=AccountNature.DEBITEUR,
        currency="XOF",
    )
    session.add(acc)
    await session.flush()
    return acc


@pytest_asyncio.fixture
async def journal_caisse(session: AsyncSession) -> Journal:
    j = Journal(
        id=str(uuid.uuid4()),
        code="CJ",
        name="Journal de Caisse",
        journal_type=JournalCode.CJ,
        sequence_prefix="CJ-",
        last_sequence=0,
    )
    session.add(j)
    await session.flush()
    return j


@pytest_asyncio.fixture
async def journal_extourne(session: AsyncSession) -> Journal:
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


# ─── Tests : Plan de comptes ──────────────────────────────────────────────────

class TestAccountService:

    @pytest.mark.asyncio
    async def test_create_account_success(self, session):
        svc = AccountService(session)
        data = AccountCreate(
            code="411000",
            name="Clients",
            account_class=AccountClass.TIERS,
            account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR,
        )
        account = await svc.create(data)
        assert account.code == "411000"
        assert account.is_leaf is True
        assert account.level == 1

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_parent_becomes_non_leaf(self, session):
        svc = AccountService(session)
        parent = await svc.create(AccountCreate(
            code="41",
            name="Clients (parent)",
            account_class=AccountClass.TIERS,
            account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR,
        ))
        assert parent.is_leaf is True

        await svc.create(AccountCreate(
            code="411000",
            name="Clients courants",
            account_class=AccountClass.TIERS,
            account_type=AccountType.ACTIF,
            account_nature=AccountNature.DEBITEUR,
            parent_id=parent.id,
        ))

        # Recharger le parent
        refreshed = await session.get(AccountPlan, parent.id)
        assert refreshed.is_leaf is False

    @pytest.mark.asyncio
    async def test_account_balance_debit_nature(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Un compte débiteur a un solde positif si débit > crédit."""
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 15),
            description="Test décaissement",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("500000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("500000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="test")
        await svc.post_entry(entry.id, posted_by="test")

        account_svc = AccountService(session)
        balance = await account_svc.get_balance(
            credit_account.id,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        assert balance["balance"] == Decimal("500000")
        assert balance["balance_nature"] == "DEBITEUR"


# ─── Tests : Partie double ────────────────────────────────────────────────────

class TestDoubleEntry:

    @pytest.mark.asyncio
    async def test_balanced_entry_accepted(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Une écriture équilibrée (ΣD = ΣC) doit être acceptée."""
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Décaissement crédit client",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("1000000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("1000000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user-1")
        assert entry.total_debit == Decimal("1000000")
        assert entry.total_credit == Decimal("1000000")
        assert entry.status == EntryStatus.DRAFT

    @pytest.mark.asyncio
    async def test_imbalanced_entry_rejected_by_schema(
        self, session, cash_account, credit_account, journal_caisse
    ):
        """Un schéma Pydantic doit rejeter une écriture déséquilibrée."""
        with pytest.raises(Exception) as exc_info:
            JournalEntryCreate(
                journal_id=journal_caisse.id,
                entry_date=date(2024, 1, 10),
                description="Écriture déséquilibrée",
                lines=[
                    JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("1000000")),
                    JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("900000")),
                ],
            )
        assert "déséquilibr" in str(exc_info.value).lower() or "imbalanced" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_line_cannot_have_both_debit_and_credit(self, session):
        """Une ligne ne peut pas avoir à la fois un débit et un crédit."""
        with pytest.raises(Exception):
            JournalLineCreate(
                account_id=str(uuid.uuid4()),
                debit_amount=Decimal("100"),
                credit_amount=Decimal("100"),
            )

    @pytest.mark.asyncio
    async def test_entry_number_is_sequential(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Les numéros d'écriture sont séquentiels par journal."""
        svc = JournalEntryService(session)
        base = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 10),
            description="Écriture test",
            lines=[
                JournalLineCreate(account_id=credit_account.id, debit_amount=Decimal("100000")),
                JournalLineCreate(account_id=cash_account.id, credit_amount=Decimal("100000")),
            ],
        )
        e1 = await svc.create_entry(base, created_by="u1")
        e2 = await svc.create_entry(base, created_by="u1")
        assert e1.entry_number != e2.entry_number
        assert e1.entry_number < e2.entry_number


# ─── Tests : Validation / Intangibilité ──────────────────────────────────────

class TestPostEntry:

    @pytest.mark.asyncio
    async def test_post_changes_status(
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

        posted = await svc.post_entry(entry.id, posted_by="supervisor")
        assert posted.status == EntryStatus.POSTED
        assert posted.posted_by == "supervisor"

    @pytest.mark.asyncio
    async def test_post_twice_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Règle d'intangibilité : impossible de valider deux fois."""
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
        await svc.post_entry(entry.id, posted_by="supervisor")

        with pytest.raises(JournalEntryAlreadyPostedError):
            await svc.post_entry(entry.id, posted_by="supervisor")

    @pytest.mark.asyncio
    async def test_post_on_closed_period_raises(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Impossible de valider une écriture si la période est clôturée."""
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 5),
            description="Test période fermée",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("75000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("75000")),
            ],
        )
        entry = await svc.create_entry(data, created_by="user")

        # Fermer la période
        open_period.status = PeriodStatus.CLOSED
        await session.flush()

        with pytest.raises(PeriodClosedError):
            await svc.post_entry(entry.id, posted_by="supervisor")


# ─── Tests : Extourne ─────────────────────────────────────────────────────────

class TestReverseEntry:

    @pytest.mark.asyncio
    async def test_reversal_inverts_debit_credit(
        self, session, cash_account, credit_account,
        journal_caisse, journal_extourne, open_period
    ):
        """L'extourne doit inverser débit et crédit de chaque ligne."""
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
        await svc.post_entry(entry.id, posted_by="supervisor")

        reversal = await svc.reverse_entry(
            entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15)
        )

        assert reversal.status == EntryStatus.POSTED
        assert reversal.total_debit == Decimal("300000")
        assert reversal.total_credit == Decimal("300000")

        # Vérifier l'inversion des lignes
        from sqlalchemy import select
        from app.models.accounting import JournalLine
        lines = list(
            (await session.execute(
                select(JournalLine).where(JournalLine.entry_id == reversal.id)
                .order_by(JournalLine.line_number)
            )).scalars().all()
        )
        # Ligne 1 : original débit → reversal crédit
        assert lines[0].credit_amount == Decimal("300000")
        assert lines[0].debit_amount == Decimal("0")
        # Ligne 2 : original crédit → reversal débit
        assert lines[1].debit_amount == Decimal("300000")
        assert lines[1].credit_amount == Decimal("0")

    @pytest.mark.asyncio
    async def test_original_marked_reversed(
        self, session, cash_account, credit_account,
        journal_caisse, journal_extourne, open_period
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
        await svc.post_entry(entry.id, posted_by="supervisor")
        await svc.reverse_entry(entry.id, reversed_by="supervisor", reversal_date=date(2024, 1, 15))

        refreshed = await session.get(type(entry), entry.id)
        assert refreshed.status == EntryStatus.REVERSED


# ─── Tests : Idempotence ──────────────────────────────────────────────────────

class TestIdempotence:

    @pytest.mark.asyncio
    async def test_same_event_id_returns_existing_entry(
        self, session, cash_account, credit_account, journal_caisse, open_period
    ):
        """Le même événement Kafka ne doit créer qu'une seule écriture."""
        svc = JournalEntryService(session)
        data = JournalEntryCreate(
            journal_id=journal_caisse.id,
            entry_date=date(2024, 1, 20),
            description="Événement idempotent",
            lines=[
                JournalLineCreate(account_id=cash_account.id, debit_amount=Decimal("50000")),
                JournalLineCreate(account_id=credit_account.id, credit_amount=Decimal("50000")),
            ],
        )
        e1 = await svc.create_entry(
            data, created_by="kafka",
            source_service="credit-service", source_event_id="evt-001"
        )
        e2 = await svc.create_entry(
            data, created_by="kafka",
            source_service="credit-service", source_event_id="evt-001"
        )
        assert e1.id == e2.id  # Même écriture retournée
