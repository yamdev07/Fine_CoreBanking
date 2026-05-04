"""
Service Comptabilité — Logique métier centrale.

Règles fondamentales implémentées :
  1. Partie double : ΣDébit = ΣCrédit (invariant systématique)
  2. Intangibilité des écritures validées (POSTED → immuable)
  3. Clôture de période : plus d'écritures possibles sur la période
  4. Idempotence : un événement externe = une seule écriture
  5. Piste d'audit complète (qui, quoi, quand)
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountAlreadyExistsError, AccountHasBalanceError, AccountHasChildrenError,
    AccountNotActiveError, FiscalYearClosedError, JournalEntryAlreadyPostedError,
    JournalEntryAlreadyReversedError, JournalEntryImbalancedError,
    JournalEntryMinimumLinesError, LetteringImbalancedError,
    LineAlreadyLetteredError, PeriodClosedError, PeriodNotFoundError,
)
from app.models.accounting import (
    AccountClass, AccountNature, AccountPlan, AccountingPeriod, EntryStatus,
    FiscalYear, FiscalYearStatus, Journal, JournalCode, JournalEntry,
    JournalLine, PeriodStatus,
)
from app.repositories.accounting import (
    AccountRepository, FiscalYearRepository, JournalEntryRepository,
    JournalRepository, PeriodRepository,
)
from app.schemas.accounting import (
    AccountCreate, AccountUpdate, FiscalYearCreate,
    JournalEntryCreate, PeriodCreate,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FiscalYearService:
    def __init__(self, session: AsyncSession):
        self.repo = FiscalYearRepository(session)
        self.period_repo = PeriodRepository(session)

    async def create(self, data: FiscalYearCreate) -> FiscalYear:
        fy = FiscalYear(
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
        )
        fy = await self.repo.create(fy)
        # Génère automatiquement les 12 périodes mensuelles
        await self._generate_monthly_periods(fy)
        return fy

    async def _generate_monthly_periods(self, fy: FiscalYear) -> None:
        from calendar import monthrange
        current = fy.start_date
        while current <= fy.end_date:
            month_end_day = monthrange(current.year, current.month)[1]
            period_end = date(current.year, current.month, month_end_day)
            if period_end > fy.end_date:
                period_end = fy.end_date

            period = AccountingPeriod(
                fiscal_year_id=fy.id,
                name=f"{current.year}-{current.month:02d}",
                start_date=current,
                end_date=period_end,
            )
            await self.period_repo.create(period)

            # Passer au mois suivant
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    async def close(self, fiscal_year_id: str, closed_by: str) -> FiscalYear:
        fy = await self.repo.get_by_id(fiscal_year_id)
        if fy.status == FiscalYearStatus.CLOSED:
            raise FiscalYearClosedError(f"L'exercice {fy.name} est déjà clôturé.")

        # Clôturer toutes les périodes ouvertes
        periods = await self.period_repo.list_by_fiscal_year(fiscal_year_id)
        for period in periods:
            if period.status == PeriodStatus.OPEN:
                period.status = PeriodStatus.LOCKED
                period.closed_at = utcnow()
                period.closed_by = closed_by

        fy.status = FiscalYearStatus.CLOSED
        fy.closed_at = utcnow()
        fy.closed_by = closed_by

        from app.services.kafka_producer import publish_fiscal_year_closed
        await publish_fiscal_year_closed(fiscal_year_id=fy.id, fiscal_year_name=fy.name)
        return fy

    async def list_all(self) -> list[FiscalYear]:
        return await self.repo.list_all()


class AccountService:
    def __init__(self, session: AsyncSession):
        self.repo = AccountRepository(session)

    async def create(self, data: AccountCreate) -> AccountPlan:
        existing = await self.repo.get_by_code(data.code)
        if existing:
            raise AccountAlreadyExistsError(f"Le compte {data.code} existe déjà.")

        level = 1
        path = ""
        parent = None

        if data.parent_id:
            parent = await self.repo.get_by_id(data.parent_id)
            level = parent.level + 1
            path = f"{parent.path}{parent.id}/"
            # Marquer le parent comme non-feuille
            parent.is_leaf = False

        account = AccountPlan(
            code=data.code,
            name=data.name,
            short_name=data.short_name,
            account_class=data.account_class,
            account_type=data.account_type,
            account_nature=data.account_nature,
            parent_id=data.parent_id,
            level=level,
            path=path,
            currency=data.currency,
            allow_manual_entry=data.allow_manual_entry,
            description=data.description,
            budget_amount=data.budget_amount,
        )
        return await self.repo.create(account)

    async def update(self, account_id: str, data: AccountUpdate) -> AccountPlan:
        account = await self.repo.get_by_id(account_id)
        updates = data.model_dump(exclude_none=True)
        return await self.repo.update(account, updates)

    async def list(
        self,
        *,
        account_class: str | None = None,
        is_active: bool | None = None,
        is_leaf: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AccountPlan], int]:
        return await self.repo.list_with_filters(
            account_class=account_class,
            is_active=is_active,
            is_leaf=is_leaf,
            search=search,
            offset=offset,
            limit=limit,
        )

    async def deactivate(self, account_id: str) -> AccountPlan:
        from datetime import date as date_cls
        account = await self.repo.get_by_id(account_id)
        children = await self.repo.get_children(account_id)
        if children:
            raise AccountHasChildrenError(
                f"Impossible de désactiver le compte {account.code} : il a des sous-comptes."
            )
        balances = await self.repo.get_balance(account_id, date_cls(2000, 1, 1), date_cls.today())
        if balances["total_debit"] != 0 or balances["total_credit"] != 0:
            raise AccountHasBalanceError(
                f"Impossible de désactiver le compte {account.code} : solde non nul."
            )
        return await self.repo.update(account, {"is_active": False})

    async def get_balance(
        self, account_id: str, start_date: date, end_date: date
    ) -> dict:
        account = await self.repo.get_by_id(account_id)
        balances = await self.repo.get_balance(account_id, start_date, end_date)
        total_debit = balances["total_debit"]
        total_credit = balances["total_credit"]

        if account.account_nature == AccountNature.DEBITEUR:
            balance = total_debit - total_credit
            nature = "DEBITEUR" if balance >= 0 else "CREDITEUR"
        else:
            balance = total_credit - total_debit
            nature = "CREDITEUR" if balance >= 0 else "DEBITEUR"

        return {
            "account_id": account_id,
            "account_code": account.code,
            "account_name": account.name,
            "account_nature": account.account_nature,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "balance": abs(balance),
            "balance_nature": nature,
            "currency": account.currency,
            "as_of_date": end_date,
        }


class JournalEntryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.entry_repo = JournalEntryRepository(session)
        self.journal_repo = JournalRepository(session)
        self.account_repo = AccountRepository(session)
        self.period_repo = PeriodRepository(session)

    async def create_entry(
        self,
        data: JournalEntryCreate,
        created_by: str,
        source_service: str | None = None,
        source_event_id: str | None = None,
    ) -> JournalEntry:
        """
        Crée une écriture comptable en brouillon (DRAFT).
        La validation de la partie double est faite par le schéma Pydantic.
        """
        # Idempotence : éviter les doublons sur replay d'événements Kafka
        if source_service and source_event_id:
            existing = await self.entry_repo.get_by_event_id(source_service, source_event_id)
            if existing:
                return existing

        journal = await self.journal_repo.get_by_id(data.journal_id)

        # Trouver la période ouverte correspondant à la date
        period = await self.period_repo.get_open_period_for_date(data.entry_date)
        if not period:
            raise PeriodNotFoundError(
                f"Aucune période ouverte trouvée pour la date {data.entry_date}."
            )

        # Vérifier que l'exercice fiscal est aussi ouvert
        fiscal_year = await self.session.get(FiscalYear, period.fiscal_year_id)
        if fiscal_year and fiscal_year.status != FiscalYearStatus.OPEN:
            raise FiscalYearClosedError(
                f"L'exercice {fiscal_year.name} est clôturé. Aucune écriture possible."
            )

        # Générer le numéro d'écriture séquentiel
        seq = await self.journal_repo.next_sequence(journal.id)
        entry_number = f"{journal.sequence_prefix}{journal.code}-{data.entry_date.year}-{seq:06d}"

        total_debit = sum(l.debit_amount for l in data.lines)
        total_credit = sum(l.credit_amount for l in data.lines)

        entry = JournalEntry(
            entry_number=entry_number,
            journal_id=journal.id,
            period_id=period.id,
            entry_date=data.entry_date,
            value_date=data.value_date or data.entry_date,
            reference=data.reference,
            description=data.description,
            total_debit=total_debit,
            total_credit=total_credit,
            currency=data.currency,
            status=EntryStatus.DRAFT,
            created_by=created_by,
            source_service=source_service,
            source_event_id=source_event_id,
        )
        entry = await self.entry_repo.create(entry)

        # Batch-fetch de tous les comptes pour éviter le N+1
        account_ids = [line_data.account_id for line_data in data.lines]
        accounts_by_id = await self.account_repo.get_by_ids(account_ids)

        # Créer les lignes
        for i, line_data in enumerate(data.lines, start=1):
            account = accounts_by_id.get(line_data.account_id)
            if not account:
                from app.core.exceptions import AccountNotFoundError
                raise AccountNotFoundError(f"Compte {line_data.account_id} introuvable.")
            if not account.is_active:
                raise AccountNotActiveError(f"Le compte {account.code} est inactif.")

            line = JournalLine(
                entry_id=entry.id,
                account_id=line_data.account_id,
                line_number=i,
                debit_amount=line_data.debit_amount,
                credit_amount=line_data.credit_amount,
                currency=data.currency,
                description=line_data.description,
                third_party_id=line_data.third_party_id,
                third_party_type=line_data.third_party_type,
            )
            self.session.add(line)

        await self.session.flush()
        return entry

    async def post_entry(self, entry_id: str, posted_by: str) -> JournalEntry:
        """
        Valide une écriture (DRAFT → POSTED).
        Une écriture validée est immuable : c'est la règle d'intangibilité.
        """
        entry = await self.entry_repo.get_by_id(entry_id, with_lines=True)

        if entry.status == EntryStatus.POSTED:
            raise JournalEntryAlreadyPostedError(
                f"L'écriture {entry.entry_number} est déjà validée."
            )
        if entry.status == EntryStatus.REVERSED:
            raise JournalEntryAlreadyReversedError(
                f"L'écriture {entry.entry_number} a été extournée."
            )

        # Revérifier l'équilibre (défense en profondeur)
        total_debit = sum(l.debit_amount for l in entry.lines)
        total_credit = sum(l.credit_amount for l in entry.lines)
        if total_debit != total_credit:
            raise JournalEntryImbalancedError(total_debit, total_credit)

        # Revérifier la période
        period = await self.period_repo.get_by_id(entry.period_id)
        if period.status != PeriodStatus.OPEN:
            raise PeriodClosedError(
                f"La période {period.name} est clôturée. Écriture impossible."
            )

        entry.status = EntryStatus.POSTED
        entry.posted_by = posted_by
        entry.posting_date = utcnow()
        await self.session.flush()
        await self.session.refresh(entry)

        from app.services.kafka_producer import publish_entry_posted
        await publish_entry_posted(
            entry_id=entry.id,
            entry_number=entry.entry_number,
            entry_date=str(entry.entry_date),
            total_debit=str(entry.total_debit),
            total_credit=str(entry.total_credit),
        )
        return entry

    async def reverse_entry(
        self, entry_id: str, reversed_by: str, reversal_date: date | None = None
    ) -> JournalEntry:
        """
        Extourne une écriture (crée l'écriture miroir avec débit/crédit inversés).
        Seules les écritures POSTED peuvent être extournées.
        """
        original = await self.entry_repo.get_by_id(entry_id, with_lines=True)

        if original.status != EntryStatus.POSTED:
            raise JournalEntryAlreadyReversedError(
                "Seules les écritures validées (POSTED) peuvent être extournées."
            )

        # Vérifier que l'écriture n'a pas déjà été extournée
        existing_reversals = await self._find_reversals(entry_id)
        if existing_reversals:
            raise JournalEntryAlreadyReversedError(
                f"L'écriture {original.entry_number} a déjà été extournée."
            )

        reversal_date = reversal_date or datetime.now(timezone.utc).date()

        # Chercher le journal d'extourne (EX)
        ex_journal = await self.journal_repo.get_by_code(JournalCode.EX.value)

        period = await self.period_repo.get_open_period_for_date(reversal_date)
        if not period:
            raise PeriodNotFoundError(
                f"Aucune période ouverte pour la date d'extourne {reversal_date}."
            )

        seq = await self.journal_repo.next_sequence(ex_journal.id)
        entry_number = f"EX-{reversal_date.year}-{seq:06d}"

        reversal = JournalEntry(
            entry_number=entry_number,
            journal_id=ex_journal.id,
            period_id=period.id,
            entry_date=reversal_date,
            value_date=reversal_date,
            description=f"Extourne de {original.entry_number} — {original.description}",
            total_debit=original.total_debit,
            total_credit=original.total_credit,
            currency=original.currency,
            status=EntryStatus.POSTED,
            created_by=reversed_by,
            posted_by=reversed_by,
            posting_date=utcnow(),
            source_entry_id=original.id,
        )
        self.session.add(reversal)
        await self.session.flush()

        # Inverser débit/crédit de chaque ligne
        for i, orig_line in enumerate(original.lines, start=1):
            rev_line = JournalLine(
                entry_id=reversal.id,
                account_id=orig_line.account_id,
                line_number=i,
                debit_amount=orig_line.credit_amount,  # Inversé
                credit_amount=orig_line.debit_amount,  # Inversé
                currency=orig_line.currency,
                description=orig_line.description,
                third_party_id=orig_line.third_party_id,
                third_party_type=orig_line.third_party_type,
            )
            self.session.add(rev_line)

        # Marquer l'originale comme extournée
        original.status = EntryStatus.REVERSED
        original.reversed_by = reversed_by
        await self.session.flush()

        return reversal

    async def _find_reversals(self, entry_id: str) -> list[JournalEntry]:
        stmt = select(JournalEntry).where(JournalEntry.source_entry_id == entry_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def letter_lines(
        self, line_ids: list[str], lettered_by: str, lettering_code: str | None = None
    ) -> dict:
        """
        Lettrage de lignes comptables (ex: rapprocher une facture et son paiement).
        Le lettrage doit être équilibré (Σdébit = Σcrédit).
        """
        stmt = select(JournalLine).where(JournalLine.id.in_(line_ids))
        result = await self.session.execute(stmt)
        lines = list(result.scalars().all())

        # Vérifier qu'aucune ligne n'est déjà lettrée
        already_lettered = [l for l in lines if l.lettering_code]
        if already_lettered:
            raise LineAlreadyLetteredError(
                f"{len(already_lettered)} ligne(s) déjà lettrée(s)."
            )

        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        if total_debit != total_credit:
            raise LetteringImbalancedError(
                f"Lettrage déséquilibré : Débit={total_debit} ≠ Crédit={total_credit}."
            )

        code = lettering_code or str(uuid.uuid4())[:8].upper()
        now = utcnow()

        for line in lines:
            line.lettering_code = code
            line.lettered_at = now
            line.lettered_by = lettered_by

        return {
            "lettering_code": code,
            "lettered_lines": len(lines),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "is_balanced": True,
        }


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.entry_repo = JournalEntryRepository(session)
        self.account_repo = AccountRepository(session)

    async def trial_balance(self, start_date: date, end_date: date) -> dict:
        """Balance générale des comptes sur une période."""
        rows = await self.entry_repo.get_trial_balance(start_date, end_date)

        lines = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for row in rows:
            if row["period_debit"] == 0 and row["period_credit"] == 0:
                continue  # Exclure les comptes sans mouvement

            d = Decimal(str(row["period_debit"]))
            c = Decimal(str(row["period_credit"]))
            total_debit += d
            total_credit += c

            lines.append({
                "account_code": row["account_code"],
                "account_name": row["account_name"],
                "account_class": AccountClass[row["account_class"]],
                "account_type": row["account_type"],
                "opening_debit": Decimal("0"),
                "opening_credit": Decimal("0"),
                "period_debit": d,
                "period_credit": c,
                "cumulative_debit": d,
                "cumulative_credit": c,
                "closing_debit": d if d > c else Decimal("0"),
                "closing_credit": c if c > d else Decimal("0"),
                "currency": row["currency"],
            })

        return {
            "period_start": start_date,
            "period_end": end_date,
            "generated_at": utcnow(),
            "lines": lines,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "is_balanced": total_debit == total_credit,
        }

    async def general_ledger(
        self, account_id: str, start_date: date, end_date: date
    ) -> dict:
        """Grand livre d'un compte avec solde progressif."""
        account = await self.account_repo.get_by_id(account_id)
        rows = await self.entry_repo.get_general_ledger(account_id, start_date, end_date)

        running_balance = Decimal("0")
        lines = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for row in rows:
            d = Decimal(str(row["debit_amount"]))
            c = Decimal(str(row["credit_amount"]))
            total_debit += d
            total_credit += c

            if account.account_nature == AccountNature.DEBITEUR:
                running_balance += d - c
            else:
                running_balance += c - d

            lines.append({
                "entry_number": row["entry_number"],
                "entry_date": row["entry_date"],
                "value_date": row["value_date"],
                "description": row["description"],
                "reference": row.get("reference"),
                "debit_amount": d,
                "credit_amount": c,
                "running_balance": running_balance,
                "balance_nature": account.account_nature.value,
            })

        return {
            "account_code": account.code,
            "account_name": account.name,
            "account_nature": account.account_nature,
            "period_start": start_date,
            "period_end": end_date,
            "opening_balance": Decimal("0"),
            "closing_balance": running_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "currency": account.currency,
            "lines": lines,
        }
