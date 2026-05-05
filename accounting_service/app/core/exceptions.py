"""
Exceptions métier du microservice comptabilité.
Chaque exception mappe vers un code HTTP précis via les handlers FastAPI.
"""

from typing import Any


class AccountingBaseError(Exception):
    """Base de toutes les exceptions métier comptables."""

    status_code: int = 500
    error_code: str = "ACCOUNTING_ERROR"

    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)


# ─── Plan de comptes ────────────────────────────────────────────────────────


class AccountNotFoundError(AccountingBaseError):
    status_code = 404
    error_code = "ACCOUNT_NOT_FOUND"


class AccountAlreadyExistsError(AccountingBaseError):
    status_code = 409
    error_code = "ACCOUNT_ALREADY_EXISTS"


class AccountNotActiveError(AccountingBaseError):
    status_code = 422
    error_code = "ACCOUNT_NOT_ACTIVE"


class AccountHasBalanceError(AccountingBaseError):
    """Impossible de supprimer un compte avec solde."""

    status_code = 422
    error_code = "ACCOUNT_HAS_BALANCE"


class AccountHasChildrenError(AccountingBaseError):
    """Impossible de supprimer un compte parent."""

    status_code = 422
    error_code = "ACCOUNT_HAS_CHILDREN"


# ─── Journaux et écritures ───────────────────────────────────────────────────


class JournalEntryImbalancedError(AccountingBaseError):
    """La somme des débits ≠ la somme des crédits. Règle de la partie double."""

    status_code = 422
    error_code = "JOURNAL_ENTRY_IMBALANCED"

    def __init__(self, total_debit, total_credit):
        super().__init__(
            f"Écriture déséquilibrée: Débit={total_debit} ≠ Crédit={total_credit}",
            details={"total_debit": str(total_debit), "total_credit": str(total_credit)},
        )


class JournalEntryNotFoundError(AccountingBaseError):
    status_code = 404
    error_code = "JOURNAL_ENTRY_NOT_FOUND"


class JournalEntryAlreadyPostedError(AccountingBaseError):
    """Une écriture validée ne peut plus être modifiée."""

    status_code = 422
    error_code = "JOURNAL_ENTRY_ALREADY_POSTED"


class JournalEntryAlreadyReversedError(AccountingBaseError):
    status_code = 422
    error_code = "JOURNAL_ENTRY_ALREADY_REVERSED"


class JournalEntryMinimumLinesError(AccountingBaseError):
    """Une écriture doit avoir au minimum 2 lignes (un débit + un crédit)."""

    status_code = 422
    error_code = "JOURNAL_ENTRY_MINIMUM_LINES"

    def __init__(self):
        super().__init__("Une écriture comptable doit comporter au moins 2 lignes.")


# ─── Périodes comptables ─────────────────────────────────────────────────────


class PeriodNotFoundError(AccountingBaseError):
    status_code = 404
    error_code = "PERIOD_NOT_FOUND"


class PeriodClosedError(AccountingBaseError):
    """Impossible d'enregistrer une écriture dans une période clôturée."""

    status_code = 422
    error_code = "PERIOD_CLOSED"


class FiscalYearNotFoundError(AccountingBaseError):
    status_code = 404
    error_code = "FISCAL_YEAR_NOT_FOUND"


class FiscalYearClosedError(AccountingBaseError):
    status_code = 422
    error_code = "FISCAL_YEAR_CLOSED"


# ─── Lettrage ────────────────────────────────────────────────────────────────


class LetteringImbalancedError(AccountingBaseError):
    """Le lettrage doit être équilibré (débit = crédit)."""

    status_code = 422
    error_code = "LETTERING_IMBALANCED"


class LineAlreadyLetteredError(AccountingBaseError):
    status_code = 422
    error_code = "LINE_ALREADY_LETTERED"


# ─── Concurrence ─────────────────────────────────────────────────────────────


class OptimisticLockError(AccountingBaseError):
    """Conflit de version — réessayer la transaction."""

    status_code = 409
    error_code = "OPTIMISTIC_LOCK_CONFLICT"
