"""
Tests unitaires — Service Reporting.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import InvalidDateRangeError
from app.services.reporting import ReportingService, pct, variation_pct


# ─── Tests utilitaires ────────────────────────────────────────────────────────

def test_pct_normal():
    assert pct(Decimal("25"), Decimal("100")) == Decimal("25.00")


def test_pct_zero_denominator():
    assert pct(Decimal("25"), Decimal("0")) is None


def test_variation_pct_positive():
    v = variation_pct(Decimal("110"), Decimal("100"))
    assert v == Decimal("10.00")


def test_variation_pct_negative():
    v = variation_pct(Decimal("80"), Decimal("100"))
    assert v == Decimal("-20.00")


def test_variation_pct_zero_previous():
    assert variation_pct(Decimal("100"), Decimal("0")) is None


# ─── Tests validation des dates ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_balance_invalid_dates():
    session = AsyncMock()
    svc = ReportingService(session)
    with pytest.raises(InvalidDateRangeError):
        await svc.trial_balance(date(2024, 12, 31), date(2024, 1, 1))


@pytest.mark.asyncio
async def test_general_ledger_invalid_dates():
    session = AsyncMock()
    svc = ReportingService(session)
    with pytest.raises(InvalidDateRangeError):
        await svc.general_ledger(
            account_id="some-id", account_code=None,
            start_date=date(2024, 6, 30), end_date=date(2024, 1, 1),
        )


# ─── Tests Balance générale ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_balance_equilibree():
    """Une balance équilibrée doit avoir total_débit == total_crédit."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_rows = [
        {
            "account_id": "1", "account_code": "411100",
            "account_name": "Clients", "account_class": "4",
            "account_type": "ACTIF", "account_nature": "DEBITEUR",
            "currency": "XOF",
            "opening_debit": "0", "opening_credit": "0",
            "period_debit": "500000", "period_credit": "0",
        },
        {
            "account_id": "2", "account_code": "571100",
            "account_name": "Caisse", "account_class": "5",
            "account_type": "ACTIF", "account_nature": "DEBITEUR",
            "currency": "XOF",
            "opening_debit": "0", "opening_credit": "0",
            "period_debit": "0", "period_credit": "500000",
        },
    ]

    with patch.object(svc.repo, "get_trial_balance", new=AsyncMock(return_value=mock_rows)):
        report = await svc.trial_balance(date(2024, 1, 1), date(2024, 1, 31))

    assert report.total_period_debit == Decimal("500000")
    assert report.total_period_credit == Decimal("500000")
    assert report.is_balanced is True
    assert report.account_count == 2


@pytest.mark.asyncio
async def test_trial_balance_soldes_cloture():
    """Les soldes de clôture doivent être corrects (débiteur ou créditeur, jamais les deux)."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_rows = [
        {
            "account_id": "1", "account_code": "571100",
            "account_name": "Caisse", "account_class": "5",
            "account_type": "ACTIF", "account_nature": "DEBITEUR",
            "currency": "XOF",
            "opening_debit": "100000", "opening_credit": "0",
            "period_debit": "200000", "period_credit": "50000",
        },
    ]

    with patch.object(svc.repo, "get_trial_balance", new=AsyncMock(return_value=mock_rows)):
        report = await svc.trial_balance(date(2024, 1, 1), date(2024, 1, 31))

    line = report.lines[0]
    assert line.cumulative_debit == Decimal("300000")
    assert line.cumulative_credit == Decimal("50000")
    assert line.closing_debit == Decimal("250000")
    assert line.closing_credit == Decimal("0")


# ─── Tests Tableau de bord ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_taux_impayes():
    """Le taux d'impayés = créances en souffrance / total portefeuille."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_fy = {
        "id": "fy1", "name": "2024",
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 12, 31),
    }
    mock_credits = [
        {"account_code": "251100", "encours": "1000000"},
        {"account_code": "257000", "encours": "100000"},  # En souffrance
    ]
    mock_depots = [
        {"code": "371100", "encours": "500000"},
    ]

    with patch.object(svc.repo, "get_fiscal_year_for_date",
                      new=AsyncMock(return_value=mock_fy)), \
         patch.object(svc.repo, "get_credit_portfolio",
                      new=AsyncMock(return_value=mock_credits)), \
         patch.object(svc.repo, "get_deposits_by_type",
                      new=AsyncMock(return_value=mock_depots)), \
         patch.object(svc.repo, "get_cash_balance",
                      new=AsyncMock(return_value=Decimal("200000"))), \
         patch.object(svc.repo, "get_net_income",
                      new=AsyncMock(return_value=Decimal("50000"))), \
         patch.object(svc.repo, "get_equity",
                      new=AsyncMock(return_value=Decimal("300000"))), \
         patch.object(svc.repo, "get_total_assets",
                      new=AsyncMock(return_value=Decimal("1500000"))), \
         patch.object(svc.repo, "get_provisions",
                      new=AsyncMock(return_value=Decimal("50000"))), \
         patch.object(svc.repo, "get_interest_charges",
                      new=AsyncMock(return_value=Decimal("10000"))), \
         patch.object(svc.repo, "get_charges_produits",
                      new=AsyncMock(return_value=[])):

        report = await svc.dashboard(date(2024, 6, 30))

    # Total crédits = 1 100 000, dont 100 000 en souffrance → 9.09%
    taux = report.kpi_taux_impayes.value
    assert Decimal("9") < taux < Decimal("10")


# ─── Tests Portefeuille crédits ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_credit_portfolio_deficit_provisionnement():
    """Le déficit = max(provisions_requises - provisions_constituées, 0)."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_credits = [
        {"account_code": "257000", "encours": "400000"},  # Souffrance
        {"account_code": "258000", "encours": "100000"},  # Irrécouvrables
    ]

    with patch.object(svc.repo, "get_credit_portfolio",
                      new=AsyncMock(return_value=mock_credits)), \
         patch.object(svc.repo, "get_provisions",
                      new=AsyncMock(return_value=Decimal("100000"))):

        report = await svc.credit_portfolio(date(2024, 6, 30))

    # Provisions requises = 50% × (400000 + 100000) = 250000
    assert report.provisions_requises == Decimal("250000")
    # Déficit = 250000 - 100000 = 150000
    assert report.deficit_provisionnement == Decimal("150000")


# ─── Tests Ratios BCEAO ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bceao_solvabilite_conforme():
    """Ratio R1 conforme si fonds_propres / actifs >= 8%."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_fy = {
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 12, 31),
    }

    with patch.object(svc.repo, "get_fiscal_year_for_date",
                      new=AsyncMock(return_value=mock_fy)), \
         patch.object(svc.repo, "get_equity",
                      new=AsyncMock(return_value=Decimal("100000"))), \
         patch.object(svc.repo, "get_total_assets",
                      new=AsyncMock(return_value=Decimal("1000000"))), \
         patch.object(svc.repo, "get_cash_balance",
                      new=AsyncMock(return_value=Decimal("200000"))), \
         patch.object(svc.repo, "get_credit_portfolio",
                      new=AsyncMock(return_value=[
                          {"account_code": "251100", "encours": "600000"}
                      ])), \
         patch.object(svc.repo, "get_deposits_by_type",
                      new=AsyncMock(return_value=[
                          {"code": "371100", "encours": "300000"},
                          {"code": "372000", "encours": "200000"},
                      ])):

        report = await svc.bceao_report(date(2024, 12, 31), "IMF-BJ-2024-001")

    # R1 = 100000 / 1000000 = 10% >= 8% → conforme
    assert report.ratio_solvabilite.conforme is True
    assert report.ratio_solvabilite.valeur >= Decimal("8")


@pytest.mark.asyncio
async def test_bceao_solvabilite_non_conforme():
    """Ratio R1 non conforme si fonds_propres / actifs < 8%."""
    session = AsyncMock()
    svc = ReportingService(session)

    mock_fy = {"start_date": date(2024, 1, 1), "end_date": date(2024, 12, 31)}

    with patch.object(svc.repo, "get_fiscal_year_for_date",
                      new=AsyncMock(return_value=mock_fy)), \
         patch.object(svc.repo, "get_equity",
                      new=AsyncMock(return_value=Decimal("50000"))), \
         patch.object(svc.repo, "get_total_assets",
                      new=AsyncMock(return_value=Decimal("2000000"))), \
         patch.object(svc.repo, "get_cash_balance",
                      new=AsyncMock(return_value=Decimal("100000"))), \
         patch.object(svc.repo, "get_credit_portfolio",
                      new=AsyncMock(return_value=[
                          {"account_code": "251100", "encours": "1500000"}
                      ])), \
         patch.object(svc.repo, "get_deposits_by_type",
                      new=AsyncMock(return_value=[
                          {"code": "371100", "encours": "800000"}
                      ])):

        report = await svc.bceao_report(date(2024, 12, 31), "IMF-BJ-2024-001")

    # R1 = 50000 / 2000000 = 2.5% < 8% → non conforme
    assert report.ratio_solvabilite.conforme is False
    assert report.observations is not None
    assert "R1" in report.observations or "Solvabilité" in report.observations
