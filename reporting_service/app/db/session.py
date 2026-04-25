"""
Session base de données — LECTURE SEULE sur la base comptabilité.
Le user PostgreSQL `reporting_ro` n'a que des droits SELECT.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

from app.core.config import settings

# Moteur en lecture seule — execution_options empêche tout write accidentel
engine = create_async_engine(
    settings.ACCOUNTING_DB_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    execution_options={"postgresql_readonly": True},
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session
