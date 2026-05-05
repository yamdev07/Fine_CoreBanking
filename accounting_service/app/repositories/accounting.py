"""
Repositories — Couche d'accès aux données.
Pattern Repository : isole la logique SQL de la logique métier.
"""
from datetime import date
from typing import Any

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    AccountingBaseError,
    AccountNotFoundError,
    FiscalYearNotFoundError,
    JournalEntryNotFoundError,
    PeriodNotFoundError,
)
from app.models.accounting import (
    AccountingPeriod,
    AccountPlan,
    EntryStatus,
    FiscalYear,
    Journal,
    JournalEntry,
    JournalLine,
    PeriodStatus,
)


class FiscalYearRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, obj: FiscalYear) -> FiscalYear:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def get_by_id(self, id: str) -> FiscalYear:
        result = await self.session.get(FiscalYear, id)
        if not result:
            raise FiscalYearNotFoundError(f"Exercice fiscal {id} introuvable.")
        return result

    async def get_by_date(self, d: date) -> FiscalYear | None:
        stmt = select(FiscalYear).where(
            FiscalYear.start_date <= d,
            FiscalYear.end_date >= d,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[FiscalYear]:
        result = await self.session.execute(
            select(FiscalYear).order_by(FiscalYear.start_date.desc())
        )
        return list(result.scalars().all())


class PeriodRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, obj: AccountingPeriod) -> AccountingPeriod:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_id(self, id: str) -> AccountingPeriod:
        result = await self.session.get(AccountingPeriod, id)
        if not result:
            raise PeriodNotFoundError(f"Période {id} introuvable.")
        return result

    async def get_open_period_for_date(self, d: date) -> AccountingPeriod | None:
        stmt = select(AccountingPeriod).where(
            AccountingPeriod.start_date <= d,
            AccountingPeriod.end_date >= d,
            AccountingPeriod.status == PeriodStatus.OPEN,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_fiscal_year(self, fiscal_year_id: str) -> list[AccountingPeriod]:
        stmt = (
            select(AccountingPeriod)
            .where(AccountingPeriod.fiscal_year_id == fiscal_year_id)
            .order_by(AccountingPeriod.start_date)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, account: AccountPlan) -> AccountPlan:
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def get_by_id(self, id: str) -> AccountPlan:
        result = await self.session.get(AccountPlan, id)
        if not result:
            raise AccountNotFoundError(f"Compte {id} introuvable.")
        return result

    async def get_by_code(self, code: str) -> AccountPlan | None:
        stmt = select(AccountPlan).where(AccountPlan.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_children(self, parent_id: str) -> list[AccountPlan]:
        stmt = select(AccountPlan).where(AccountPlan.parent_id == parent_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_with_filters(
        self,
        *,
        account_class: str | None = None,
        is_active: bool | None = None,
        is_leaf: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AccountPlan], int]:
        stmt = select(AccountPlan)
        count_stmt = select(func.count()).select_from(AccountPlan)

        filters = []
        if account_class:
            filters.append(AccountPlan.account_class == account_class)
        if is_active is not None:
            filters.append(AccountPlan.is_active == is_active)
        if is_leaf is not None:
            filters.append(AccountPlan.is_leaf == is_leaf)
        if search:
            pattern = f"%{search}%"
            filters.append(
                AccountPlan.code.ilike(pattern) | AccountPlan.name.ilike(pattern)
            )

        if filters:
            stmt = stmt.where(and_(*filters))
            count_stmt = count_stmt.where(and_(*filters))

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list(
            (
                await self.session.execute(
                    stmt.order_by(AccountPlan.code).offset(offset).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return items, total

    async def get_balance(
        self,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Calcule débit/crédit/solde d'un compte sur une période."""
        stmt = (
            select(
                func.coalesce(func.sum(JournalLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalLine.credit_amount), 0).label("total_credit"),
            )
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == account_id,
                JournalEntry.status == EntryStatus.POSTED,
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
            )
        )
        row = (await self.session.execute(stmt)).one()
        return {"total_debit": row.total_debit, "total_credit": row.total_credit}

    async def get_by_ids(self, ids: list[str]) -> dict[str, "AccountPlan"]:
        """Batch-fetch pour éviter le N+1."""
        stmt = select(AccountPlan).where(AccountPlan.id.in_(ids))
        rows = (await self.session.execute(stmt)).scalars().all()
        return {a.id: a for a in rows}

    async def update(self, account: AccountPlan, data: dict[str, Any]) -> AccountPlan:
        from app.core.exceptions import OptimisticLockError
        current_version = account.version
        stmt = (
            update(AccountPlan)
            .where(AccountPlan.id == account.id, AccountPlan.version == current_version)
            .values(**data, version=current_version + 1)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError(
                f"Conflit de version sur le compte {account.code} — réessayez."
            )
        await self.session.refresh(account)
        return account


class JournalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: str) -> Journal:
        result = await self.session.get(Journal, id)
        if not result:
            raise AccountingBaseError(f"Journal {id} introuvable.")
        return result

    async def get_by_code(self, code: str) -> Journal | None:
        stmt = select(Journal).where(Journal.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[Journal]:
        result = await self.session.execute(
            select(Journal).where(Journal.is_active).order_by(Journal.code)
        )
        return list(result.scalars().all())

    async def create(self, journal: Journal) -> Journal:
        self.session.add(journal)
        await self.session.flush()
        return journal

    async def next_sequence(self, journal_id: str) -> int:
        """Incrémente atomiquement le compteur de séquence du journal."""
        stmt = (
            update(Journal)
            .where(Journal.id == journal_id)
            .values(last_sequence=Journal.last_sequence + 1)
            .returning(Journal.last_sequence)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class JournalEntryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, entry: JournalEntry) -> JournalEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_by_id(self, id: str, *, with_lines: bool = False) -> JournalEntry:
        if with_lines:
            stmt = (
                select(JournalEntry)
                .options(
                    selectinload(JournalEntry.journal),
                    selectinload(JournalEntry.lines).selectinload(JournalLine.account),
                )
                .where(JournalEntry.id == id)
            )
            result = (await self.session.execute(stmt)).scalar_one_or_none()
        else:
            result = await self.session.get(JournalEntry, id)

        if not result:
            raise JournalEntryNotFoundError(f"Écriture {id} introuvable.")
        return result

    async def get_by_event_id(self, service: str, event_id: str) -> JournalEntry | None:
        """Idempotence : vérifie si l'événement a déjà été traité."""
        stmt = select(JournalEntry).where(
            JournalEntry.source_service == service,
            JournalEntry.source_event_id == event_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_period(
        self,
        period_id: str | None,
        *,
        status: EntryStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[JournalEntry], int]:
        stmt = select(JournalEntry).options(
            selectinload(JournalEntry.journal),
            selectinload(JournalEntry.lines),
        )
        count_stmt = select(func.count()).select_from(JournalEntry)
        if period_id:
            stmt = stmt.where(JournalEntry.period_id == period_id)
            count_stmt = count_stmt.where(JournalEntry.period_id == period_id)
        if status:
            stmt = stmt.where(JournalEntry.status == status)
            count_stmt = count_stmt.where(JournalEntry.status == status)

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list(
            (
                await self.session.execute(
                    stmt.order_by(JournalEntry.entry_date, JournalEntry.entry_number)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return items, total

    async def get_trial_balance(self, start_date: date, end_date: date) -> list[dict]:
        """Balance générale : agrégation par compte."""
        stmt = """
            SELECT
                ap.id          AS account_id,
                ap.code        AS account_code,
                ap.name        AS account_name,
                ap.account_class,
                ap.account_type,
                ap.account_nature,
                ap.currency,
                COALESCE(SUM(CASE WHEN je.status = 'POSTED'
                                   AND je.entry_date BETWEEN :start_date AND :end_date
                                  THEN jl.debit_amount  ELSE 0 END), 0) AS period_debit,
                COALESCE(SUM(CASE WHEN je.status = 'POSTED'
                                   AND je.entry_date BETWEEN :start_date AND :end_date
                                  THEN jl.credit_amount ELSE 0 END), 0) AS period_credit
            FROM account_plans ap
            LEFT JOIN journal_lines jl ON jl.account_id = ap.id
            LEFT JOIN journal_entries je ON je.id = jl.entry_id
            WHERE ap.is_leaf = TRUE
            GROUP BY ap.id, ap.code, ap.name, ap.account_class,
                     ap.account_type, ap.account_nature, ap.currency
            ORDER BY ap.code
        """
        rows = (
            await self.session.execute(
                text(stmt),
                {"start_date": str(start_date), "end_date": str(end_date)},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def get_general_ledger(
        self, account_id: str, start_date: date, end_date: date
    ) -> list[dict]:
        """Grand livre d'un compte avec solde progressif."""
        stmt = """
            SELECT
                je.entry_number,
                je.entry_date,
                je.value_date,
                je.description,
                je.reference,
                jl.debit_amount,
                jl.credit_amount
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
              AND je.entry_date BETWEEN :start_date AND :end_date
            ORDER BY je.entry_date, je.entry_number, jl.line_number
        """
        # UUID(as_uuid=False) stores without hyphens in SQLite; strip them so
        # text() comparisons work on both SQLite (tests) and PostgreSQL (prod).
        rows = (
            await self.session.execute(
                text(stmt),
                {
                    "account_id": account_id.replace("-", ""),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                },
            )
        ).mappings().all()
        return [dict(r) for r in rows]
