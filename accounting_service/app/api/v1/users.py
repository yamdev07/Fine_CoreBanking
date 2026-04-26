"""
Gestion des utilisateurs — Endpoints CRUD (AdminOnly).
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AdminOnly, AnyAuthenticated, TokenPayload
from app.db.session import get_session
from app.models.auth import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services.auth import hash_password

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.get("", response_model=list[UserOut], summary="Liste des utilisateurs")
async def list_users(
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).order_by(User.created_at))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Créer un utilisateur")
async def create_user(
    body: UserCreate,
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    # Check uniqueness
    existing = await session.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "USER_EXISTS", "message": "Nom d'utilisateur ou email déjà utilisé."},
        )
    user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    await session.flush()
    logger.info("users.created", username=user.username, role=user.role.value, by=principal.sub)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut, summary="Détail d'un utilisateur")
async def get_user(
    user_id: str,
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_or_404(session, user_id)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Mettre à jour un utilisateur")
async def update_user(
    user_id: str,
    body: UserUpdate,
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_or_404(session, user_id)
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.hashed_password = hash_password(body.password)
    logger.info("users.updated", user_id=user_id, by=principal.sub)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Désactiver un utilisateur")
async def deactivate_user(
    user_id: str,
    principal: AdminOnly,
    session: AsyncSession = Depends(get_session),
):
    if user_id == principal.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "SELF_DEACTIVATION", "message": "Impossible de se désactiver soi-même."},
        )
    user = await _get_or_404(session, user_id)
    user.is_active = False
    logger.info("users.deactivated", user_id=user_id, by=principal.sub)


async def _get_or_404(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "USER_NOT_FOUND", "message": "Utilisateur introuvable."},
        )
    return user
