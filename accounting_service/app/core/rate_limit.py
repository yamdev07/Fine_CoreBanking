"""
Per-user, per-role rate limiting key function for SlowAPI.

Key: JWT subject (sub claim) → rate limit scoped per user, not per IP.
Limit: varies by role — ADMIN gets more headroom than AUDITOR.
Falls back to IP for unauthenticated requests (login endpoint).
"""
from fastapi import Request
from jose import JWTError, jwt

from app.core.config import settings

ROLE_LIMITS: dict[str, str] = {
    "ADMIN": "1000/minute",
    "ACCOUNTANT": "200/minute",
    "AUDITOR": "100/minute",
}
DEFAULT_LIMIT = "60/minute"


def _extract_payload(request: Request) -> dict | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(
            auth[7:],
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        return None


def get_jwt_subject(request: Request) -> str:
    """SlowAPI key_func — returns 'user:<sub>' or 'ip:<addr>'."""
    payload = _extract_payload(request)
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{ip}"


def get_user_limit(request: Request) -> str:
    """Dynamic limit string based on JWT role."""
    payload = _extract_payload(request)
    if payload:
        for role in payload.get("roles", []):
            if role in ROLE_LIMITS:
                return ROLE_LIMITS[role]
    return DEFAULT_LIMIT
