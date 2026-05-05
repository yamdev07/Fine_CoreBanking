"""
Sécurité Zero Trust — Microservice Comptabilité.

Principe : chaque requête est authentifiée et autorisée indépendamment,
même si elle provient d'un autre microservice interne.

Flux :
  1. Extraction du Bearer token (HTTPBearer)
  2. Validation de la signature JWT (python-jose)
  3. Vérification de l'expiration
  4. Contrôle des rôles (RBAC)
  5. Propagation du principal dans la requête
"""

import enum
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = structlog.get_logger(__name__)

http_bearer = HTTPBearer(auto_error=False)

# Refuse de démarrer si la clé secrète est celle par défaut en production
if settings.ENVIRONMENT == "production" and settings.JWT_SECRET_KEY == "change-me-in-production":
    raise RuntimeError("JWT_SECRET_KEY doit être changée en production.")


# ─── Rôles ────────────────────────────────────────────────────────────────────


class Role(enum.StrEnum):
    ADMIN = "ADMIN"  # Accès total
    ACCOUNTANT = "ACCOUNTANT"  # Saisie et validation des écritures
    AUDITOR = "AUDITOR"  # Lecture seule
    SERVICE_CREDIT = "SERVICE_CREDIT"  # Microservice Crédit (M2M)
    SERVICE_SAVINGS = "SERVICE_SAVINGS"  # Microservice Épargne (M2M)
    SERVICE_CASH = "SERVICE_CASH"  # Microservice Caisse (M2M)


# ─── Modèle du token ──────────────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Contenu attendu dans le JWT."""

    sub: str  # Identifiant du sujet (user id ou nom du service)
    roles: list[Role] = []  # Rôles attribués
    service: str | None = None  # Renseigné pour les tokens M2M inter-services
    exp: int  # Obligatoire — un token sans expiration est rejeté


# ─── Décodage et validation du token ─────────────────────────────────────────


def _decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except ExpiredSignatureError:
        logger.warning("jwt_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_EXPIRED", "message": "Token expiré."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValidationError) as exc:
        logger.warning("jwt_invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Token invalide ou malformé."},
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Dépendance principale ────────────────────────────────────────────────────


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> TokenPayload:
    """Extrait et valide le JWT de chaque requête entrante."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_MISSING", "message": "Token d'authentification requis."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = _decode_token(credentials.credentials)

    logger.info(
        "request_authenticated",
        subject=principal.sub,
        roles=[r.value for r in principal.roles],
        service=principal.service,
    )
    return principal


# ─── Contrôle d'accès par rôle (RBAC) ────────────────────────────────────────


def require_roles(*allowed_roles: Role):
    """
    Fabrique de dépendances RBAC.
    Lève HTTP 403 si le principal n'a aucun des rôles autorisés.
    """
    allowed = frozenset(allowed_roles)

    async def _checker(
        principal: TokenPayload = Depends(get_current_principal),
    ) -> TokenPayload:
        if not any(r in allowed for r in principal.roles):
            logger.warning(
                "access_denied",
                subject=principal.sub,
                required=[r.value for r in allowed],
                granted=[r.value for r in principal.roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": "Droits insuffisants pour cette opération.",
                },
            )
        return principal

    return _checker


# ─── Niveaux d'accès prêts à l'emploi (Annotated) ────────────────────────────

# Tout utilisateur authentifié (lecture)
AnyAuthenticated = Annotated[
    TokenPayload,
    Depends(get_current_principal),
]

# Comptables et administrateurs (écriture humaine)
WriteAccess = Annotated[
    TokenPayload,
    Depends(require_roles(Role.ADMIN, Role.ACCOUNTANT)),
]

# Services internes + comptables (création d'écritures automatiques)
ServiceOrWrite = Annotated[
    TokenPayload,
    Depends(
        require_roles(
            Role.ADMIN,
            Role.ACCOUNTANT,
            Role.SERVICE_CREDIT,
            Role.SERVICE_SAVINGS,
            Role.SERVICE_CASH,
        )
    ),
]

# Administrateur uniquement (opérations destructives)
AdminOnly = Annotated[
    TokenPayload,
    Depends(require_roles(Role.ADMIN)),
]
