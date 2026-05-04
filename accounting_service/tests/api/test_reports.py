"""
API tests — Rapports comptables
Couvre : balance générale, grand livre, dates invalides, permissions.
"""
import pytest
from decimal import Decimal
from httpx import AsyncClient

from tests.conftest import CASH_ACCOUNT_ID, CREDIT_ACCOUNT_ID, CAISSE_JOURNAL_ID


def balanced_entry(amount: str = "1000000") -> dict:
    return {
        "journal_id": CAISSE_JOURNAL_ID,
        "entry_date": "2024-01-15",
        "description": "Écriture pour rapport",
        "lines": [
            {"account_id": CASH_ACCOUNT_ID, "debit_amount": amount},
            {"account_id": CREDIT_ACCOUNT_ID, "credit_amount": amount},
        ],
    }


class TestTrialBalance:

    async def test_trial_balance_empty_period(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            "/api/v1/reports/trial-balance",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert "lines" in body
        assert "total_debit" in body
        assert "total_credit" in body
        assert "is_balanced" in body
        # No posted entries → totals are 0
        assert body["total_debit"] == "0"
        assert body["total_credit"] == "0"
        assert body["is_balanced"] is True

    async def test_trial_balance_with_posted_entries(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        # Create and post an entry
        create_res = await api_client.post("/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers)
        entry_id = create_res.json()["id"]
        await api_client.post(f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers)

        res = await api_client.get(
            "/api/v1/reports/trial-balance",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        body = res.json()
        # At least the two accounts should appear
        assert len(body["lines"]) >= 2
        assert body["is_balanced"] is True
        # Total debit == total credit (double entry invariant)
        assert body["total_debit"] == body["total_credit"]

    async def test_trial_balance_invalid_date_range_returns_422(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            "/api/v1/reports/trial-balance",
            params={"start_date": "2024-12-31", "end_date": "2024-01-01"},
            headers=auditor_headers,
        )
        assert res.status_code == 422

    async def test_trial_balance_missing_dates_returns_422(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/reports/trial-balance", headers=auditor_headers)
        assert res.status_code == 422

    async def test_trial_balance_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.get(
            "/api/v1/reports/trial-balance",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        )
        assert res.status_code == 401

    async def test_draft_entries_excluded_from_trial_balance(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        # Create but do NOT post
        await api_client.post("/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers)

        res = await api_client.get(
            "/api/v1/reports/trial-balance",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        # DRAFT entries not included
        assert res.json()["total_debit"] == "0"


class TestGeneralLedger:

    async def test_general_ledger_empty(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            f"/api/v1/reports/general-ledger/{CASH_ACCOUNT_ID}",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["account_code"] == "571100"
        assert body["lines"] == []
        assert body["total_debit"] == "0"
        assert body["total_credit"] == "0"

    async def test_general_ledger_with_posted_entries(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        create_res = await api_client.post("/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers)
        entry_id = create_res.json()["id"]
        await api_client.post(f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers)

        res = await api_client.get(
            f"/api/v1/reports/general-ledger/{CASH_ACCOUNT_ID}",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert len(body["lines"]) == 1
        assert Decimal(body["lines"][0]["debit_amount"]) == Decimal("1000000")
        assert body["closing_balance"] is not None

    async def test_general_ledger_nonexistent_account_returns_404(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            "/api/v1/reports/general-ledger/00000000-0000-0000-0000-deadbeef0001",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 404

    async def test_general_ledger_running_balance_progression(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        """Solde progressif augmente correctement après chaque écriture."""
        for _ in range(3):
            create_res = await api_client.post(
                "/api/v1/journal-entries/", json=balanced_entry("100000"), headers=accountant_headers
            )
            await api_client.post(f"/api/v1/journal-entries/{create_res.json()['id']}/post", headers=accountant_headers)

        res = await api_client.get(
            f"/api/v1/reports/general-ledger/{CASH_ACCOUNT_ID}",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        lines = res.json()["lines"]
        assert len(lines) == 3
        balances = [float(l["running_balance"]) for l in lines]
        # Each debit of 100000 → balance grows
        assert balances[0] < balances[1] < balances[2]
