"""
Sécurité JWT — Microservice Reporting (lecture seule).
Valide les tokens émis par le microservice Comptabilité.
"""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = structlog.get_logger(__name__)

http_bearer = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    roles: list[str] = []
    exp: int


def _decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_EXPIRED", "message": "Token expiré."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Token invalide."},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_MISSING", "message": "Token d'authentification requis."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_token(credentials.credentials)


AnyAuthenticated = Annotated[TokenPayload, Depends(get_current_principal)]
