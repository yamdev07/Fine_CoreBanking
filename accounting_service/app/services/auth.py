"""
Service d'authentification — hachage de mots de passe, émission de tokens JWT.
"""

from datetime import UTC, datetime, timedelta

import structlog
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import Role
from app.models.auth import User, UserRole

logger = structlog.get_logger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mapping UserRole → JWT Role
_ROLE_MAP: dict[UserRole, Role] = {
    UserRole.ADMIN: Role.ADMIN,
    UserRole.ACCOUNTANT: Role.ACCOUNTANT,
    UserRole.AUDITOR: Role.AUDITOR,
}


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    exp = datetime.now(UTC) + timedelta(seconds=expires_in)
    payload = {
        "sub": user.id,
        "roles": [_ROLE_MAP[user.role].value],
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    user.last_login_at = datetime.now(UTC)
    return user


async def seed_admin(session: AsyncSession) -> None:
    """Crée l'admin par défaut si aucun utilisateur n'existe."""
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    admin = User(
        username="admin",
        full_name="Administrateur",
        email="admin@core-banking.local",
        hashed_password=hash_password("Admin1234!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    logger.info("auth.seed_admin_created", username="admin")
