"""Exceptions métier du microservice Reporting."""
from typing import Any


class ReportingBaseError(Exception):
    status_code: int = 500
    error_code: str = "REPORTING_ERROR"

    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)


class ReportNotFoundError(ReportingBaseError):
    status_code = 404
    error_code = "REPORT_NOT_FOUND"


class InvalidDateRangeError(ReportingBaseError):
    status_code = 422
    error_code = "INVALID_DATE_RANGE"


class FiscalYearNotFoundError(ReportingBaseError):
    status_code = 404
    error_code = "FISCAL_YEAR_NOT_FOUND"


class AccountNotFoundError(ReportingBaseError):
    status_code = 404
    error_code = "ACCOUNT_NOT_FOUND"


class ExportError(ReportingBaseError):
    status_code = 500
    error_code = "EXPORT_ERROR"


class PeriodNotClosedError(ReportingBaseError):
    """Certains rapports réglementaires nécessitent une période clôturée."""
    status_code = 422
    error_code = "PERIOD_NOT_CLOSED"
