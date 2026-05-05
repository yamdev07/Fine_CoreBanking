"""
API tests — Plan de comptes
Couvre : CRUD comptes, permissions par rôle, filtres, solde.
"""
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import (
    CASH_ACCOUNT_ID,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

NEW_ACCOUNT = {
    "code": "411000",
    "name": "Clients courants",
    "account_class": "4",
    "account_type": "ACTIF",
    "account_nature": "DEBITEUR",
    "currency": "XOF",
}


class TestCreateAccount:

    async def test_create_account_success(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT, headers=admin_headers)
        assert res.status_code == 201
        body = res.json()
        assert body["code"] == "411000"
        assert body["is_leaf"] is True
        assert body["level"] == 1
        assert body["is_active"] is True

    async def test_create_account_by_accountant_allowed(self, api_client: AsyncClient, accountant_headers: dict):
        res = await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT, headers=accountant_headers)
        assert res.status_code == 201

    async def test_create_account_by_auditor_forbidden(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT, headers=auditor_headers)
        assert res.status_code == 403

    async def test_create_account_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT)
        assert res.status_code == 401

    async def test_create_duplicate_account_returns_409(self, api_client: AsyncClient, admin_headers: dict):
        await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT, headers=admin_headers)
        res = await api_client.post("/api/v1/accounts/", json=NEW_ACCOUNT, headers=admin_headers)
        assert res.status_code == 409

    async def test_create_account_with_parent_sets_hierarchy(self, api_client: AsyncClient, admin_headers: dict):
        parent_res = await api_client.post("/api/v1/accounts/", json={
            "code": "41",
            "name": "Clients (classe)",
            "account_class": "4",
            "account_type": "ACTIF",
            "account_nature": "DEBITEUR",
        }, headers=admin_headers)
        assert parent_res.status_code == 201
        parent_id = parent_res.json()["id"]

        child_res = await api_client.post("/api/v1/accounts/", json={
            **NEW_ACCOUNT,
            "parent_id": parent_id,
        }, headers=admin_headers)
        assert child_res.status_code == 201
        child = child_res.json()
        assert child["level"] == 2
        assert child["parent_id"] == parent_id

        # Parent must now be a non-leaf
        parent_check = await api_client.get(f"/api/v1/accounts/{parent_id}", headers=admin_headers)
        assert parent_check.json()["is_leaf"] is False

    async def test_create_account_invalid_code_not_digits(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/accounts/", json={
            **NEW_ACCOUNT, "code": "ABC",
        }, headers=admin_headers)
        assert res.status_code == 422


class TestListAccounts:

    async def test_list_accounts_returns_paginated(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/accounts/", headers=auditor_headers)
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert body["page"] == 1
        assert body["total"] >= 2  # cash + credit seeded

    async def test_list_accounts_filter_by_active(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/accounts/?is_active=true", headers=auditor_headers)
        assert res.status_code == 200
        for acc in res.json()["items"]:
            assert acc["is_active"] is True

    async def test_list_accounts_search_by_code(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/accounts/?search=571100", headers=auditor_headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        assert items[0]["code"] == "571100"

    async def test_list_accounts_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.get("/api/v1/accounts/")
        assert res.status_code == 401


class TestGetAccount:

    async def test_get_existing_account(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(f"/api/v1/accounts/{CASH_ACCOUNT_ID}", headers=auditor_headers)
        assert res.status_code == 200
        assert res.json()["code"] == "571100"

    async def test_get_nonexistent_account_returns_404(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/accounts/00000000-0000-0000-0000-deadbeef0000", headers=auditor_headers)
        assert res.status_code == 404


class TestUpdateAccount:

    async def test_update_account_name(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.patch(
            f"/api/v1/accounts/{CASH_ACCOUNT_ID}",
            json={"name": "Caisse principale modifiée"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Caisse principale modifiée"

    async def test_update_account_auditor_forbidden(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.patch(
            f"/api/v1/accounts/{CASH_ACCOUNT_ID}",
            json={"name": "Tentative illicite"},
            headers=auditor_headers,
        )
        assert res.status_code == 403


class TestDeactivateAccount:

    async def test_deactivate_requires_admin(self, api_client: AsyncClient, accountant_headers: dict):
        res = await api_client.delete(f"/api/v1/accounts/{CASH_ACCOUNT_ID}", headers=accountant_headers)
        assert res.status_code == 403

    async def test_deactivate_account_with_no_balance(self, api_client: AsyncClient, admin_headers: dict):
        # Create a fresh account with no movements
        create_res = await api_client.post("/api/v1/accounts/", json={
            "code": "999999",
            "name": "Compte à désactiver",
            "account_class": "6",
            "account_type": "CHARGE",
            "account_nature": "DEBITEUR",
        }, headers=admin_headers)
        assert create_res.status_code == 201
        acc_id = create_res.json()["id"]

        res = await api_client.delete(f"/api/v1/accounts/{acc_id}", headers=admin_headers)
        assert res.status_code == 204


class TestAccountBalance:

    async def test_get_balance_no_movements(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            f"/api/v1/accounts/{CASH_ACCOUNT_ID}/balance",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=auditor_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert Decimal(body["total_debit"]) == Decimal("0")
        assert Decimal(body["total_credit"]) == Decimal("0")
        assert Decimal(body["balance"]) == Decimal("0")
        assert body["currency"] == "XOF"

    async def test_get_balance_missing_dates_returns_422(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(
            f"/api/v1/accounts/{CASH_ACCOUNT_ID}/balance",
            headers=auditor_headers,
        )
        assert res.status_code == 422
