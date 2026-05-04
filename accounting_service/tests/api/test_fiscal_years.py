"""
API tests — Exercices fiscaux et périodes
Couvre : création, lecture, clôture, périodes générées.
"""
import pytest
from httpx import AsyncClient

from tests.conftest import FISCAL_YEAR_ID, ADMIN_ID


VALID_FISCAL_YEAR = {
    "name": "2025",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
}


class TestCreateFiscalYear:

    async def test_create_fiscal_year_success(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR, headers=admin_headers)
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "2025"
        assert body["status"] == "OPEN"
        assert body["closed_at"] is None

    async def test_create_fiscal_year_generates_12_periods(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR, headers=admin_headers)
        assert res.status_code == 201
        fy_id = res.json()["id"]

        periods_res = await api_client.get(f"/api/v1/fiscal-years/{fy_id}/periods", headers=admin_headers)
        assert periods_res.status_code == 200
        periods = periods_res.json()
        assert len(periods) == 12
        assert periods[0]["name"] == "2025-01"
        assert periods[11]["name"] == "2025-12"
        for p in periods:
            assert p["status"] == "OPEN"

    async def test_create_fiscal_year_invalid_dates_returns_422(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/fiscal-years/", json={
            "name": "BAD",
            "start_date": "2025-12-31",
            "end_date": "2025-01-01",  # end before start
        }, headers=admin_headers)
        assert res.status_code == 422

    async def test_create_fiscal_year_auditor_forbidden(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR, headers=auditor_headers)
        assert res.status_code == 403

    async def test_create_fiscal_year_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR)
        assert res.status_code == 401


class TestListFiscalYears:

    async def test_list_fiscal_years(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/fiscal-years/", headers=auditor_headers)
        assert res.status_code == 200
        fy_list = res.json()
        assert isinstance(fy_list, list)
        assert any(fy["id"] == FISCAL_YEAR_ID for fy in fy_list)

    async def test_list_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.get("/api/v1/fiscal-years/")
        assert res.status_code == 401


class TestGetFiscalYear:

    async def test_get_by_id(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(f"/api/v1/fiscal-years/{FISCAL_YEAR_ID}", headers=auditor_headers)
        assert res.status_code == 200
        assert res.json()["name"] == "2024"

    async def test_get_nonexistent_returns_404(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/fiscal-years/00000000-0000-0000-0000-deadbeef0001", headers=auditor_headers)
        assert res.status_code == 404

    async def test_list_periods_of_seeded_fy(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(f"/api/v1/fiscal-years/{FISCAL_YEAR_ID}/periods", headers=auditor_headers)
        assert res.status_code == 200
        periods = res.json()
        # Only one period was seeded (Jan 2024)
        assert len(periods) == 1
        assert periods[0]["name"] == "2024-01"

    async def test_periods_of_nonexistent_fy_returns_404(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get("/api/v1/fiscal-years/00000000-0000-0000-0000-deadbeef0001/periods", headers=auditor_headers)
        assert res.status_code == 404


class TestCloseFiscalYear:

    async def test_close_fiscal_year_success(self, api_client: AsyncClient, admin_headers: dict):
        # Create a fresh FY to close
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR, headers=admin_headers)
        assert res.status_code == 201
        fy_id = res.json()["id"]

        close_res = await api_client.post(f"/api/v1/fiscal-years/{fy_id}/close", headers=admin_headers)
        assert close_res.status_code == 200
        body = close_res.json()
        assert body["status"] == "CLOSED"
        assert body["closed_by"] == ADMIN_ID
        assert body["closed_at"] is not None

    async def test_close_already_closed_returns_409(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/fiscal-years/", json=VALID_FISCAL_YEAR, headers=admin_headers)
        fy_id = res.json()["id"]
        await api_client.post(f"/api/v1/fiscal-years/{fy_id}/close", headers=admin_headers)

        # Second close
        res2 = await api_client.post(f"/api/v1/fiscal-years/{fy_id}/close", headers=admin_headers)
        assert res2.status_code == 409
        assert res2.json()["detail"]["error_code"] == "FISCAL_YEAR_ALREADY_CLOSED"

    async def test_close_fiscal_year_auditor_forbidden(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.post(f"/api/v1/fiscal-years/{FISCAL_YEAR_ID}/close", headers=auditor_headers)
        assert res.status_code == 403
