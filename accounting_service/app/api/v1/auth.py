"""
Endpoints d'authentification.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AnyAuthenticated
from app.db.session import get_session
from app.models.auth import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth import authenticate_user, create_access_token

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentification"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=TokenResponse, summary="Connexion")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_user(session, body.username, body.password)
    if user is None:
        logger.warning("auth.login_failed", username=body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Identifiants incorrects."},
        )
    token, expires_in = create_access_token(user)
    logger.info("auth.login_success", username=user.username, role=user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut, summary="Profil courant")
async def me(
    principal: AnyAuthenticated,
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    result = await session.execute(
        select(User).where(User.id == principal.sub)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "USER_NOT_FOUND", "message": "Utilisateur introuvable."},
        )
    return UserOut.model_validate(user)
