"""
Modèles SQLAlchemy — Microservice Comptabilité.

Plan de comptes (PCG adapté SYSCOHADA/BCEAO) :
  Classe 1 : Comptes de capitaux
  Classe 2 : Comptes d'actifs immobilisés
  Classe 3 : Comptes de stocks
  Classe 4 : Comptes de tiers
  Classe 5 : Comptes de trésorerie
  Classe 6 : Comptes de charges
  Classe 7 : Comptes de produits
  Classe 8 : Comptes spéciaux
  Classe 9 : Comptes analytiques
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum,
    ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


# ─── Enums ───────────────────────────────────────────────────────────────────

class AccountClass(str, enum.Enum):
    CAPITAL = "1"
    IMMOBILISE = "2"
    STOCK = "3"
    TIERS = "4"
    TRESORERIE = "5"
    CHARGES = "6"
    PRODUITS = "7"
    SPECIAUX = "8"
    ANALYTIQUE = "9"


class AccountType(str, enum.Enum):
    ACTIF = "ACTIF"
    PASSIF = "PASSIF"
    CHARGE = "CHARGE"
    PRODUIT = "PRODUIT"


class AccountNature(str, enum.Enum):
    """Sens normal du solde."""
    DEBITEUR = "DEBITEUR"   # Actifs, Charges
    CREDITEUR = "CREDITEUR"  # Passifs, Produits


class JournalCode(str, enum.Enum):
    GJ = "GJ"    # Journal Général
    CJ = "CJ"    # Journal de Caisse
    BJ = "BJ"    # Journal de Banque
    OD = "OD"    # Opérations Diverses
    AN = "AN"    # À-Nouveau (report exercice)
    EX = "EX"    # Extourne
    CR = "CR"    # Crédits
    EP = "EP"    # Épargne
    IB = "IB"    # Interbancaire (banque commerciale)
    TR = "TR"    # Titres et valeurs mobilières
    LC = "LC"    # Lettres de crédit / engagements hors-bilan
    FX = "FX"    # Change et devises


class EntryStatus(str, enum.Enum):
    DRAFT = "DRAFT"       # Brouillon (modifiable)
    POSTED = "POSTED"     # Validé (immuable)
    REVERSED = "REVERSED"  # Extourné


class PeriodStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"  # Verrouillé après clôture annuelle


class FiscalYearStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"  # En cours de clôture
    CLOSED = "CLOSED"


# ─── Exercice fiscal ─────────────────────────────────────────────────────────

class FiscalYear(Base):
    __tablename__ = "fiscal_years"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(20), nullable=False)         # ex: "2024"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FiscalYearStatus] = mapped_column(
        Enum(FiscalYearStatus), nullable=False, default=FiscalYearStatus.OPEN
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    periods: Mapped[list["AccountingPeriod"]] = relationship(
        back_populates="fiscal_year", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name"),
        CheckConstraint("end_date > start_date", name="ck_fiscal_year_dates"),
    )


# ─── Période comptable ────────────────────────────────────────────────────────

class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    fiscal_year_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("fiscal_years.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(20), nullable=False)   # ex: "2024-01"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus), nullable=False, default=PeriodStatus.OPEN
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(100))

    fiscal_year: Mapped["FiscalYear"] = relationship(back_populates="periods")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="period")

    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "name"),
        CheckConstraint("end_date > start_date", name="ck_period_dates"),
        Index("ix_period_dates", "start_date", "end_date"),
    )


# ─── Plan de comptes ──────────────────────────────────────────────────────────

class AccountPlan(Base):
    """Plan de comptes — hiérarchie arborescente (auto-référentielle)."""
    __tablename__ = "account_plans"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(20), nullable=False)   # ex: "411100"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))

    account_class: Mapped[AccountClass] = mapped_column(Enum(AccountClass), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    account_nature: Mapped[AccountNature] = mapped_column(Enum(AccountNature), nullable=False)

    # Hiérarchie
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("account_plans.id")
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Code chemin pour requêtes hiérarchiques rapides : "1/4/41/411/4111/"
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    is_leaf: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_manual_entry: Mapped[bool] = mapped_column(Boolean, default=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")
    description: Mapped[str | None] = mapped_column(Text)

    # Contraintes budgétaires optionnelles
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, default=1)  # Optimistic locking

    parent: Mapped["AccountPlan | None"] = relationship(
        "AccountPlan", remote_side="AccountPlan.id", back_populates="children"
    )
    children: Mapped[list["AccountPlan"]] = relationship(
        "AccountPlan", back_populates="parent"
    )
    ledger_lines: Mapped[list["JournalLine"]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("code", name="uq_account_code"),
        Index("ix_account_code", "code"),
        Index("ix_account_path", "path"),
        Index("ix_account_class", "account_class"),
    )

    def __repr__(self) -> str:
        return f"<AccountPlan {self.code} - {self.name}>"


# ─── Journal comptable ────────────────────────────────────────────────────────

class Journal(Base):
    """Journaux auxiliaires (Caisse, Banque, Crédits, Épargne, OD, ...)."""
    __tablename__ = "journals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    journal_type: Mapped[JournalCode] = mapped_column(Enum(JournalCode), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Séquenceur propre à chaque journal
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sequence_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    entries: Mapped[list["JournalEntry"]] = relationship(back_populates="journal")

    __table_args__ = (UniqueConstraint("code"),)


# ─── Écriture comptable (en-tête) ─────────────────────────────────────────────

class JournalEntry(Base):
    """
    En-tête d'écriture comptable.
    Règle fondamentale : ΣDébit = ΣCrédit (partie double).
    """
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    entry_number: Mapped[str] = mapped_column(String(30), nullable=False)  # ex: GJ-2024-000001
    journal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("journals.id"), nullable=False
    )
    period_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("accounting_periods.id"), nullable=False
    )

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)  # Date de valeur
    posting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reference: Mapped[str | None] = mapped_column(String(100))  # Réf. pièce justificative
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Totaux (dénormalisés pour performances)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")

    status: Mapped[EntryStatus] = mapped_column(
        Enum(EntryStatus), nullable=False, default=EntryStatus.DRAFT
    )

    # Traçabilité
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    posted_by: Mapped[str | None] = mapped_column(String(100))
    reversed_by: Mapped[str | None] = mapped_column(String(100))

    # Lien vers écriture source (pour extournes)
    source_entry_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("journal_entries.id")
    )
    # Origine inter-microservices
    source_service: Mapped[str | None] = mapped_column(String(50))  # ex: "credit-service"
    source_event_id: Mapped[str | None] = mapped_column(String(100))  # Idempotence

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    journal: Mapped["Journal"] = relationship(back_populates="entries")
    period: Mapped["AccountingPeriod"] = relationship(back_populates="journal_entries")
    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLine.line_number"
    )
    source_entry: Mapped["JournalEntry | None"] = relationship(
        "JournalEntry", remote_side="JournalEntry.id"
    )

    @property
    def journal_code(self) -> str | None:
        j = self.__dict__.get("journal")
        return j.code if j else None

    __table_args__ = (
        UniqueConstraint("entry_number", name="uq_entry_number"),
        UniqueConstraint("source_service", "source_event_id", name="uq_event_idempotence"),
        Index("ix_entry_date", "entry_date"),
        Index("ix_entry_status", "status"),
        Index("ix_entry_period", "period_id"),
        CheckConstraint(
            "status != 'POSTED' OR total_debit = total_credit",
            name="ck_entry_balanced_when_posted"
        ),
    )


# ─── Ligne d'écriture ─────────────────────────────────────────────────────────

class JournalLine(Base):
    """
    Ligne d'écriture (mouvement élémentaire sur un compte).
    Un mouvement est soit Débit, soit Crédit — jamais les deux.
    """
    __tablename__ = "journal_lines"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("journal_entries.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("account_plans.id"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")

    description: Mapped[str | None] = mapped_column(Text)

    # Données auxiliaires (ex: id client, numéro de crédit, ...)
    third_party_id: Mapped[str | None] = mapped_column(String(100))
    third_party_type: Mapped[str | None] = mapped_column(String(50))  # CLIENT | FOURNISSEUR

    # Lettrage (rapprochement)
    lettering_code: Mapped[str | None] = mapped_column(String(20))
    lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lettered_by: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["AccountPlan"] = relationship(back_populates="ledger_lines")

    __table_args__ = (
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_line_debit_xor_credit"
        ),
        CheckConstraint("debit_amount >= 0 AND credit_amount >= 0", name="ck_line_positive"),
        Index("ix_line_account", "account_id"),
        Index("ix_line_lettering", "lettering_code"),
        Index("ix_line_third_party", "third_party_id"),
    )
