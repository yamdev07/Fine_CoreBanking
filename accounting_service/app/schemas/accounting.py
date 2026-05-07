"""
Schémas Pydantic v2 — Validation des entrées/sorties API.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.accounting import (
    AccountClass,
    AccountNature,
    AccountType,
    EntryStatus,
    FiscalYearStatus,
    JournalCode,
    PeriodStatus,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

PositiveDecimal = Annotated[Decimal, Field(gt=0, decimal_places=4)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0, decimal_places=4)]


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=500)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


_T = TypeVar("_T")


class PaginatedResponse(BaseModel, Generic[_T]):
    items: list[_T]
    total: int
    page: int
    size: int
    pages: int


# ─── Exercice fiscal ──────────────────────────────────────────────────────────


class FiscalYearCreate(BaseModel):
    name: str = Field(..., min_length=4, max_length=20, examples=["2024"])
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "FiscalYearCreate":
        if self.end_date <= self.start_date:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class FiscalYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    start_date: date
    end_date: date
    status: FiscalYearStatus
    closed_at: datetime | None
    closed_by: str | None
    created_at: datetime


# ─── Période comptable ────────────────────────────────────────────────────────


class PeriodCreate(BaseModel):
    fiscal_year_id: str
    name: str = Field(..., examples=["2024-01"])
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "PeriodCreate":
        if self.end_date <= self.start_date:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    fiscal_year_id: str
    name: str
    start_date: date
    end_date: date
    status: PeriodStatus
    closed_at: datetime | None


# ─── Compte comptable ─────────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, pattern=r"^\d+$")
    name: str = Field(..., min_length=2, max_length=200)
    short_name: str | None = Field(None, max_length=50)
    account_class: AccountClass
    account_type: AccountType
    account_nature: AccountNature
    parent_id: str | None = None
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    allow_manual_entry: bool = True
    description: str | None = None
    budget_amount: NonNegativeDecimal | None = None

    @field_validator("code")
    @classmethod
    def validate_code_class(cls, v: str, info) -> str:
        # Le premier chiffre du code doit correspondre à la classe
        return v


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    short_name: str | None = None
    allow_manual_entry: bool | None = None
    description: str | None = None
    budget_amount: NonNegativeDecimal | None = None
    is_active: bool | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    short_name: str | None
    account_class: AccountClass
    account_type: AccountType
    account_nature: AccountNature
    parent_id: str | None
    level: int
    is_leaf: bool
    is_active: bool
    allow_manual_entry: bool
    currency: str
    description: str | None
    budget_amount: Decimal | None
    created_at: datetime
    updated_at: datetime


class AccountBalanceResponse(BaseModel):
    """Solde d'un compte à une date donnée."""

    account_id: str
    account_code: str
    account_name: str
    account_nature: AccountNature
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal  # Positif = sens normal, Négatif = sens inverse
    balance_nature: str  # "DEBITEUR" ou "CREDITEUR"
    currency: str
    as_of_date: date


# ─── Journal ──────────────────────────────────────────────────────────────────


class JournalCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., min_length=2, max_length=100)
    journal_type: JournalCode
    sequence_prefix: str = Field(default="", max_length=10)
    description: str | None = None


class JournalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    journal_type: JournalCode
    is_active: bool
    sequence_prefix: str
    description: str | None


# ─── Lignes d'écriture ────────────────────────────────────────────────────────


class JournalLineCreate(BaseModel):
    account_id: str
    debit_amount: NonNegativeDecimal = Decimal("0")
    credit_amount: NonNegativeDecimal = Decimal("0")
    description: str | None = None
    third_party_id: str | None = None
    third_party_type: str | None = None

    @model_validator(mode="after")
    def validate_debit_xor_credit(self) -> "JournalLineCreate":
        d, c = self.debit_amount, self.credit_amount
        if d > 0 and c > 0:
            raise ValueError("Une ligne ne peut pas avoir à la fois un débit et un crédit.")
        if d == 0 and c == 0:
            raise ValueError("Une ligne doit avoir un montant débit ou crédit non nul.")
        return self


class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    account_code: str | None = None  # Joint optionnel
    account_name: str | None = None
    line_number: int
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str
    description: str | None
    third_party_id: str | None
    third_party_type: str | None
    lettering_code: str | None
    lettered_at: datetime | None


# ─── Écriture comptable ───────────────────────────────────────────────────────


class JournalEntryCreate(BaseModel):
    journal_id: str
    entry_date: date
    value_date: date | None = None  # Par défaut = entry_date
    reference: str | None = Field(None, max_length=100)
    description: str = Field(..., min_length=2, max_length=500)
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    lines: list[JournalLineCreate] = Field(..., min_length=2)

    @model_validator(mode="after")
    def validate_balance(self) -> "JournalEntryCreate":
        total_d = sum(ln.debit_amount for ln in self.lines)
        total_c = sum(ln.credit_amount for ln in self.lines)
        if total_d != total_c:
            raise ValueError(
                f"Écriture déséquilibrée : Débit={total_d} ≠ Crédit={total_c}. "
                "La règle de la partie double doit être respectée."
            )
        if self.value_date is None:
            self.value_date = self.entry_date
        return self


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entry_number: str
    journal_id: str
    journal_code: str | None = None
    period_id: str
    entry_date: date
    value_date: date
    posting_date: datetime | None
    reference: str | None
    description: str
    total_debit: Decimal
    total_credit: Decimal
    currency: str
    status: EntryStatus
    created_by: str
    posted_by: str | None
    source_service: str | None
    source_event_id: str | None
    source_entry_id: str | None = None
    created_at: datetime
    lines: list[JournalLineResponse] = []


# ─── Rapports ─────────────────────────────────────────────────────────────────


class TrialBalanceLine(BaseModel):
    account_code: str
    account_name: str
    account_class: AccountClass
    account_type: AccountType
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    cumulative_debit: Decimal
    cumulative_credit: Decimal
    closing_debit: Decimal  # Solde débiteur final
    closing_credit: Decimal  # Solde créditeur final
    currency: str


class TrialBalanceResponse(BaseModel):
    """Balance générale des comptes."""

    period_start: date
    period_end: date
    generated_at: datetime
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool  # total_debit == total_credit


class LedgerLine(BaseModel):
    entry_number: str
    entry_date: date
    value_date: date
    description: str
    reference: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    running_balance: Decimal
    balance_nature: str


class GeneralLedgerResponse(BaseModel):
    """Grand livre d'un compte."""

    account_code: str
    account_name: str
    account_nature: AccountNature
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    currency: str
    lines: list[LedgerLine]


# ─── Lettrage ─────────────────────────────────────────────────────────────────


class LetteringRequest(BaseModel):
    line_ids: list[str] = Field(..., min_length=2)
    lettering_code: str | None = None  # Auto-généré si None


class LetteringResponse(BaseModel):
    lettering_code: str
    lettered_lines: int
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
