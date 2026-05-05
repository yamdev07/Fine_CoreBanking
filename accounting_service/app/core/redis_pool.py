"""Singleton Redis pool — import get_redis() everywhere instead of creating new connections."""
import redis.asyncio as aioredis
from app.core.config import settings

_pool: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _pool

async def close_redis_pool() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
