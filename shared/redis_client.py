"""Async Redis client helpers for working memory, cache, and checkpoints."""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from shared.config import get_settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Return the global async Redis client."""
    global _redis  # noqa: PLW0603
    if _redis is None:
        settings = get_settings()
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close the global Redis client."""
    global _redis  # noqa: PLW0603
    if _redis is not None:
        await _redis.close()
        _redis = None


async def working_memory_get(session_id: str) -> dict[str, Any] | None:
    """Fetch the current working memory for a session."""
    client = await get_redis()
    data = await client.get(f"wm:{session_id}")
    if data is None:
        return None
    import json

    return json.loads(data)


async def working_memory_set(
    session_id: str, data: dict[str, Any], ttl: int | None = 3600
) -> None:
    """Store working memory for a session with optional TTL."""
    import json

    client = await get_redis()
    await client.set(f"wm:{session_id}", json.dumps(data, default=str), ex=ttl)


async def embedding_cache_get(text: str) -> list[float] | None:
    """Try to fetch a cached embedding vector. Redis failure is non-fatal."""
    import hashlib
    import json

    key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
    try:
        client = await get_redis()
        cached = await client.get(key)
        if cached:
            return json.loads(cached)
    except Exception:  # noqa: BLE001
        pass
    return None


async def embedding_cache_set(text: str, vector: list[float], ttl: int = 86_400) -> None:
    """Cache an embedding vector. Redis failure is non-fatal."""
    import hashlib
    import json

    key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
    try:
        client = await get_redis()
        await client.set(key, json.dumps(vector), ex=ttl)
    except Exception:  # noqa: BLE001
        pass
