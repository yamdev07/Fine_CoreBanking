"""
API tests — Gestion des utilisateurs (AdminOnly)
Couvre : CRUD, restrictions de rôle, unicité.
"""
import pytest
from httpx import AsyncClient

from tests.conftest import ADMIN_ID, ACCOUNTANT_ID, AUDITOR_ID


NEW_USER = {
    "username": "nouveau",
    "full_name": "Nouveau Utilisateur",
    "email": "nouveau@example.com",
    "password": "Nouveau1234!",
    "role": "AUDITOR",
}


class TestListUsers:

    async def test_list_users_admin_success(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.get("/api/v1/users", headers=admin_headers)
        assert res.status_code == 200
        users = res.json()
        assert isinstance(users, list)
        assert len(users) >= 3  # admin + accountant + auditor seeded
        usernames = [u["username"] for u in users]
        assert "admin" in usernames

    async def test_list_users_accountant_forbidden(self, api_client: AsyncClient, accountant_headers: dict):
        res = await api_client.get("/api/v1/users", headers=accountant_headers)
        assert res.status_code == 403

    async def test_list_users_unauthenticated(self, api_client: AsyncClient):
        res = await api_client.get("/api/v1/users")
        assert res.status_code == 401


class TestCreateUser:

    async def test_create_user_success(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
        assert res.status_code == 201
        body = res.json()
        assert body["username"] == "nouveau"
        assert body["role"] == "AUDITOR"
        assert body["is_active"] is True
        assert "hashed_password" not in body

    async def test_create_user_duplicate_username_returns_409(self, api_client: AsyncClient, admin_headers: dict):
        await api_client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
        res = await api_client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
        assert res.status_code == 409
        assert res.json()["detail"]["error_code"] == "USER_EXISTS"

    async def test_create_user_duplicate_email_returns_409(self, api_client: AsyncClient, admin_headers: dict):
        await api_client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
        res = await api_client.post("/api/v1/users", json={
            **NEW_USER,
            "username": "other_username",  # different username, same email
        }, headers=admin_headers)
        assert res.status_code == 409

    async def test_create_user_non_admin_forbidden(self, api_client: AsyncClient, accountant_headers: dict):
        res = await api_client.post("/api/v1/users", json=NEW_USER, headers=accountant_headers)
        assert res.status_code == 403


class TestGetUser:

    async def test_get_user_by_id(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.get(f"/api/v1/users/{ADMIN_ID}", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["username"] == "admin"

    async def test_get_nonexistent_user_returns_404(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.get("/api/v1/users/00000000-0000-0000-0000-deadbeef1234", headers=admin_headers)
        assert res.status_code == 404

    async def test_get_user_non_admin_forbidden(self, api_client: AsyncClient, auditor_headers: dict):
        res = await api_client.get(f"/api/v1/users/{ADMIN_ID}", headers=auditor_headers)
        assert res.status_code == 403


class TestUpdateUser:

    async def test_update_user_full_name(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.patch(
            f"/api/v1/users/{ACCOUNTANT_ID}",
            json={"full_name": "Comptable Senior"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["full_name"] == "Comptable Senior"

    async def test_update_user_role(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.patch(
            f"/api/v1/users/{AUDITOR_ID}",
            json={"role": "ACCOUNTANT"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["role"] == "ACCOUNTANT"

    async def test_update_user_password(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.patch(
            f"/api/v1/users/{AUDITOR_ID}",
            json={"password": "NewPassword1234!"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        # Verify new password works
        login_res = await api_client.post("/api/v1/auth/login", json={
            "username": "auditor", "password": "NewPassword1234!",
        })
        assert login_res.status_code == 200


class TestDeactivateUser:

    async def test_deactivate_user_success(self, api_client: AsyncClient, admin_headers: dict):
        # Create a user to deactivate
        create_res = await api_client.post("/api/v1/users", json=NEW_USER, headers=admin_headers)
        user_id = create_res.json()["id"]

        res = await api_client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert res.status_code == 204

        # Deactivated user cannot login
        login_res = await api_client.post("/api/v1/auth/login", json={
            "username": "nouveau", "password": "Nouveau1234!",
        })
        assert login_res.status_code == 401

    async def test_cannot_deactivate_self_returns_400(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.delete(f"/api/v1/users/{ADMIN_ID}", headers=admin_headers)
        assert res.status_code == 400
        assert res.json()["detail"]["error_code"] == "SELF_DEACTIVATION"

    async def test_deactivate_nonexistent_user_returns_404(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.delete("/api/v1/users/00000000-0000-0000-0000-deadbeef5678", headers=admin_headers)
        assert res.status_code == 404
