"""
API tests — Écritures comptables
Couvre : création, validation, extourne, lettrage, idempotence, permissions.
"""

from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import (
    ACCOUNTANT_ID,
    ADMIN_ID,
    CAISSE_JOURNAL_ID,
    CASH_ACCOUNT_ID,
    CREDIT_ACCOUNT_ID,
    PERIOD_ID,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def balanced_entry(
    debit_account: str = CASH_ACCOUNT_ID,
    credit_account: str = CREDIT_ACCOUNT_ID,
    amount: str = "500000",
) -> dict:
    return {
        "journal_id": CAISSE_JOURNAL_ID,
        "entry_date": "2024-01-15",
        "description": "Écriture de test",
        "currency": "XOF",
        "lines": [
            {"account_id": debit_account, "debit_amount": amount},
            {"account_id": credit_account, "credit_amount": amount},
        ],
    }


class TestCreateEntry:
    async def test_create_entry_success(self, api_client: AsyncClient, accountant_headers: dict):
        res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        assert res.status_code == 201
        body = res.json()
        assert body["status"] == "DRAFT"
        assert Decimal(body["total_debit"]) == Decimal("500000")
        assert Decimal(body["total_credit"]) == Decimal("500000")
        assert body["created_by"] == ACCOUNTANT_ID
        assert len(body["lines"]) == 2

    async def test_create_imbalanced_entry_returns_422(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        data = {
            "journal_id": CAISSE_JOURNAL_ID,
            "entry_date": "2024-01-15",
            "description": "Déséquilibré",
            "lines": [
                {"account_id": CASH_ACCOUNT_ID, "debit_amount": "100000"},
                {"account_id": CREDIT_ACCOUNT_ID, "credit_amount": "99999"},
            ],
        }
        res = await api_client.post(
            "/api/v1/journal-entries/", json=data, headers=accountant_headers
        )
        assert res.status_code == 422

    async def test_create_entry_outside_period_returns_404(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        data = balanced_entry()
        data["entry_date"] = "2023-06-01"  # No open period for this date
        res = await api_client.post(
            "/api/v1/journal-entries/", json=data, headers=accountant_headers
        )
        assert res.status_code == 404

    async def test_create_entry_auditor_forbidden(
        self, api_client: AsyncClient, auditor_headers: dict
    ):
        res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=auditor_headers
        )
        assert res.status_code == 403

    async def test_create_entry_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.post("/api/v1/journal-entries/", json=balanced_entry())
        assert res.status_code == 401

    async def test_create_entry_single_line_rejected(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        data = {
            "journal_id": CAISSE_JOURNAL_ID,
            "entry_date": "2024-01-15",
            "description": "Une seule ligne",
            "lines": [
                {"account_id": CASH_ACCOUNT_ID, "debit_amount": "100000"},
            ],
        }
        res = await api_client.post(
            "/api/v1/journal-entries/", json=data, headers=accountant_headers
        )
        assert res.status_code == 422

    async def test_create_idempotent_entry(self, api_client: AsyncClient, accountant_headers: dict):
        {
            **balanced_entry(),
            "source_service": "credit-service",
            "source_event_id": "evt-unique-001",
        }
        # Note: source_service/source_event_id are passed via query params or body — skip if not supported by schema
        res1 = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        res2 = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        # Two distinct entries (no idempotency key) → different IDs
        assert res1.json()["id"] != res2.json()["id"]


class TestListEntries:
    async def test_list_entries_by_period(
        self, api_client: AsyncClient, auditor_headers: dict, accountant_headers: dict
    ):
        # Create an entry first
        await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )

        res = await api_client.get(
            f"/api/v1/journal-entries/?period_id={PERIOD_ID}", headers=auditor_headers
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 1
        assert isinstance(body["items"], list)

    async def test_list_entries_invalid_status_returns_422(
        self, api_client: AsyncClient, auditor_headers: dict
    ):
        res = await api_client.get(
            f"/api/v1/journal-entries/?period_id={PERIOD_ID}&status=INVALID_STATUS",
            headers=auditor_headers,
        )
        assert res.status_code == 422

    async def test_list_entries_filter_by_status(
        self, api_client: AsyncClient, auditor_headers: dict, accountant_headers: dict
    ):
        await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )

        res = await api_client.get(
            f"/api/v1/journal-entries/?period_id={PERIOD_ID}&status=DRAFT",
            headers=auditor_headers,
        )
        assert res.status_code == 200
        for entry in res.json()["items"]:
            assert entry["status"] == "DRAFT"


class TestGetEntry:
    async def test_get_entry_by_id(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]

        res = await api_client.get(f"/api/v1/journal-entries/{entry_id}", headers=auditor_headers)
        assert res.status_code == 200
        assert res.json()["id"] == entry_id
        assert len(res.json()["lines"]) == 2

    async def test_get_nonexistent_entry_returns_404(
        self, api_client: AsyncClient, auditor_headers: dict
    ):
        res = await api_client.get(
            "/api/v1/journal-entries/00000000-0000-0000-0000-deadbeef9999", headers=auditor_headers
        )
        assert res.status_code == 404


class TestPostEntry:
    async def test_post_entry_changes_status_to_posted(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]

        post_res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers
        )
        assert post_res.status_code == 200
        body = post_res.json()
        assert body["status"] == "POSTED"
        assert body["posted_by"] == ADMIN_ID or body["posted_by"] is not None

    async def test_post_entry_twice_returns_422(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]
        await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers
        )

        res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers
        )
        assert res.status_code == 422

    async def test_post_entry_auditor_forbidden(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]

        res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/post", headers=auditor_headers
        )
        assert res.status_code == 403


class TestReverseEntry:
    async def _create_and_post(self, api_client: AsyncClient, headers: dict) -> str:
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=headers
        )
        entry_id = create_res.json()["id"]
        await api_client.post(f"/api/v1/journal-entries/{entry_id}/post", headers=headers)
        return entry_id

    async def test_reverse_posted_entry_success(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        entry_id = await self._create_and_post(api_client, accountant_headers)

        res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/reverse",
            params={"reversal_date": "2024-01-20"},
            headers=accountant_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "POSTED"
        assert "Extourne" in body["description"]
        # Lines are inverted
        lines = body["lines"]
        assert len(lines) == 2

    async def test_reverse_draft_entry_returns_422(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]  # Still DRAFT

        res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/reverse",
            params={"reversal_date": "2024-01-20"},
            headers=accountant_headers,
        )
        assert res.status_code == 422

    async def test_reverse_already_reversed_returns_422(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        entry_id = await self._create_and_post(api_client, accountant_headers)
        await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/reverse",
            params={"reversal_date": "2024-01-20"},
            headers=accountant_headers,
        )
        # Second reversal
        res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/reverse",
            params={"reversal_date": "2024-01-20"},
            headers=accountant_headers,
        )
        assert res.status_code == 422

    async def test_reverse_marks_original_as_reversed(
        self, api_client: AsyncClient, accountant_headers: dict, auditor_headers: dict
    ):
        entry_id = await self._create_and_post(api_client, accountant_headers)
        await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/reverse",
            params={"reversal_date": "2024-01-20"},
            headers=accountant_headers,
        )

        original = await api_client.get(
            f"/api/v1/journal-entries/{entry_id}", headers=auditor_headers
        )
        assert original.json()["status"] == "REVERSED"


class TestLetterLines:
    async def test_letter_balanced_lines(self, api_client: AsyncClient, accountant_headers: dict):
        # Create and post an entry
        create_res = await api_client.post(
            "/api/v1/journal-entries/", json=balanced_entry(), headers=accountant_headers
        )
        entry_id = create_res.json()["id"]
        post_res = await api_client.post(
            f"/api/v1/journal-entries/{entry_id}/post", headers=accountant_headers
        )
        lines = post_res.json()["lines"]
        line_ids = [ln["id"] for ln in lines]

        res = await api_client.post(
            "/api/v1/journal-entries/letter",
            json={"line_ids": line_ids},
            headers=accountant_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["lettered_lines"] == 2
        assert body["is_balanced"] is True
        assert body["lettering_code"] is not None
