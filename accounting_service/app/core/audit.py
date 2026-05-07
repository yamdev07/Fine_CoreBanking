"""
Middleware d'audit — enregistre toutes les mutations (POST/PUT/PATCH/DELETE).
Chaque écriture est non-bloquante (fire-and-forget via asyncio.create_task).
"""

import time

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

logger = structlog.get_logger(__name__)

AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIP_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in AUDIT_METHODS or request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Extract principal from JWT (best-effort — don't block on failure)
        user_id = username = user_role = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth_header[7:],
                    settings.JWT_SECRET_KEY,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                user_id = payload.get("sub")
                username = payload.get("username")
                roles: list[str] = payload.get("roles", [])
                user_role = roles[0] if roles else None
            except JWTError:
                pass

        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)

        # Persist asynchronously to avoid slowing down the response
        import asyncio

        asyncio.create_task(
            _persist_audit(
                user_id=user_id,
                username=username,
                user_role=user_role,
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                ip_address=ip,
                duration_ms=duration_ms,
            )
        )

        return response


async def _persist_audit(**kwargs) -> None:
    try:
        from app.db.session import AsyncSessionFactory
        from app.models.audit import AuditLog

        async with AsyncSessionFactory() as session:
            async with session.begin():
                session.add(AuditLog(**kwargs))
    except Exception as exc:
        logger.warning("audit.persist_failed", error=str(exc))
