"""
Cache Redis — mémorise les rapports lourds pour éviter de recalculer.
Clé : "report:{type}:{params_hash}"
"""

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def make_cache_key(report_type: str, params: dict) -> str:
    """Génère une clé de cache déterministe depuis les paramètres du rapport."""
    params_str = json.dumps(params, sort_keys=True, default=str)
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
    return f"report:{report_type}:{params_hash}"


async def get_cached(key: str) -> Any | None:
    try:
        r = await get_redis()
        data = await r.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


async def set_cached(key: str, value: Any, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass  # Cache best-effort — ne pas bloquer si Redis est down


async def invalidate_pattern(pattern: str) -> None:
    try:
        r = await get_redis()
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
    except Exception:
        pass
