"""
API tests — Authentification
Couvre : login, /me, token expiré, token manquant, utilisateur inactif.
"""

from httpx import AsyncClient

from tests.conftest import ADMIN_ID


class TestLogin:
    async def test_login_success_returns_token(self, api_client: AsyncClient):
        res = await api_client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "Admin1234!",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "ADMIN"

    async def test_login_wrong_password_returns_401(self, api_client: AsyncClient):
        res = await api_client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "WrongPassword!",
            },
        )
        assert res.status_code == 401
        assert res.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"

    async def test_login_unknown_user_returns_401(self, api_client: AsyncClient):
        res = await api_client.post(
            "/api/v1/auth/login",
            json={
                "username": "ghost",
                "password": "Admin1234!",
            },
        )
        assert res.status_code == 401

    async def test_login_missing_body_returns_422(self, api_client: AsyncClient):
        res = await api_client.post("/api/v1/auth/login", json={})
        assert res.status_code == 422

    async def test_login_inactive_user_returns_401(
        self, api_client: AsyncClient, admin_headers: dict
    ):
        # Deactivate the accountant first
        res = await api_client.delete(
            "/api/v1/users/10000000-0000-0000-0000-000000000002", headers=admin_headers
        )
        assert res.status_code == 204

        res = await api_client.post(
            "/api/v1/auth/login",
            json={
                "username": "accountant",
                "password": "Acc1234!",
            },
        )
        assert res.status_code == 401


class TestMe:
    async def test_me_with_valid_token(self, api_client: AsyncClient, admin_headers: dict):
        res = await api_client.get("/api/v1/auth/me", headers=admin_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == ADMIN_ID
        assert body["username"] == "admin"

    async def test_me_without_token_returns_401(self, api_client: AsyncClient):
        res = await api_client.get("/api/v1/auth/me")
        assert res.status_code == 401
        assert res.json()["detail"]["error_code"] == "TOKEN_MISSING"

    async def test_me_with_expired_token_returns_401(
        self, api_client: AsyncClient, expired_token_headers: dict
    ):
        res = await api_client.get("/api/v1/auth/me", headers=expired_token_headers)
        assert res.status_code == 401
        assert res.json()["detail"]["error_code"] == "TOKEN_EXPIRED"

    async def test_me_with_malformed_token_returns_401(self, api_client: AsyncClient):
        res = await api_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"}
        )
        assert res.status_code == 401
        assert res.json()["detail"]["error_code"] == "TOKEN_INVALID"

    async def test_me_returns_correct_role_for_accountant(
        self, api_client: AsyncClient, accountant_headers: dict
    ):
        res = await api_client.get("/api/v1/auth/me", headers=accountant_headers)
        assert res.status_code == 200
        assert res.json()["role"] == "ACCOUNTANT"
