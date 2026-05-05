"""
Modèles SQLAlchemy pour les tests d'intégration.
Miroir des modèles du service comptabilité (lecture seule en prod).
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

# SQLite-compatible UUID (stocké comme string)
from sqlalchemy import String as SAString
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


class AccountClass(enum.StrEnum):
    CAPITAL = "1"
    IMMOBILISE = "2"
    STOCK = "3"
    TIERS = "4"
    TRESORERIE = "5"
    CHARGES = "6"
    PRODUITS = "7"
    SPECIAUX = "8"
    ANALYTIQUE = "9"


class AccountType(enum.StrEnum):
    ACTIF = "ACTIF"
    PASSIF = "PASSIF"
    CHARGE = "CHARGE"
    PRODUIT = "PRODUIT"


class AccountNature(enum.StrEnum):
    DEBITEUR = "DEBITEUR"
    CREDITEUR = "CREDITEUR"


class JournalCode(enum.StrEnum):
    GJ = "GJ"
    CJ = "CJ"
    BJ = "BJ"
    OD = "OD"
    AN = "AN"
    EX = "EX"
    CR = "CR"
    EP = "EP"


class EntryStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class PeriodStatus(enum.StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"


class FiscalYearStatus(enum.StrEnum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("name"),)


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    fiscal_year_id: Mapped[str] = mapped_column(
        SAString(36), ForeignKey("fiscal_years.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("fiscal_year_id", "name"),)


class AccountPlan(Base):
    __tablename__ = "account_plans"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    account_class: Mapped[str] = mapped_column(String(5), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_nature: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(SAString(36), ForeignKey("account_plans.id"))
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_manual_entry: Mapped[bool] = mapped_column(Boolean, default=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")
    description: Mapped[str | None] = mapped_column(Text)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("code", name="uq_account_code"),)


class Journal(Base):
    __tablename__ = "journals"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    journal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sequence_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("code"),)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    entry_number: Mapped[str] = mapped_column(String(30), nullable=False)
    journal_id: Mapped[str] = mapped_column(SAString(36), ForeignKey("journals.id"), nullable=False)
    period_id: Mapped[str] = mapped_column(
        SAString(36), ForeignKey("accounting_periods.id"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reference: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    posted_by: Mapped[str | None] = mapped_column(String(100))
    reversed_by: Mapped[str | None] = mapped_column(String(100))
    source_entry_id: Mapped[str | None] = mapped_column(
        SAString(36), ForeignKey("journal_entries.id")
    )
    source_service: Mapped[str | None] = mapped_column(String(50))
    source_event_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("entry_number", name="uq_entry_number"),)


class JournalLine(Base):
    __tablename__ = "journal_lines"
    id: Mapped[str] = mapped_column(SAString(36), primary_key=True, default=new_uuid)
    entry_id: Mapped[str] = mapped_column(
        SAString(36), ForeignKey("journal_entries.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        SAString(36), ForeignKey("account_plans.id"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")
    description: Mapped[str | None] = mapped_column(Text)
    third_party_id: Mapped[str | None] = mapped_column(String(100))
    third_party_type: Mapped[str | None] = mapped_column(String(50))
    lettering_code: Mapped[str | None] = mapped_column(String(20))
    lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lettered_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
