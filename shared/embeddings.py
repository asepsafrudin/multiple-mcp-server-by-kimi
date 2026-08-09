"""Async embedding client backed by Ollama, with Redis caching."""

from __future__ import annotations

import json
import math

import httpx

from shared.config import get_settings
from shared.redis_client import embedding_cache_get, embedding_cache_set


class EmbeddingError(RuntimeError):
    pass


def _normalize(vector: list[float]) -> list[float]:
    """L2-normalise a vector so distance metrics are comparable."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


async def get_embedding(text: str, *, force_refresh: bool = False) -> list[float]:
    """Generate a normalised vector embedding via local Ollama, using Redis cache."""
    settings = get_settings()
    text = text[:2000]  # guard against huge payloads

    if not force_refresh:
        cached = await embedding_cache_get(text)
        if cached:
            return _normalize(cached)

    payload = {
        "model": settings.ollama_embedding_model,
        "prompt": text,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/embeddings",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    embedding = data.get("embedding")
    if not embedding or not isinstance(embedding, list):
        raise EmbeddingError(f"Unexpected Ollama response: {json.dumps(data)[:200]}")

    normalized = _normalize(embedding)
    await embedding_cache_set(text, normalized)
    return normalized


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch embeddings sequentially with caching.

    Ollama does not expose a true batch endpoint, so we iterate with caching.
    """
    return [await get_embedding(t) for t in texts]
