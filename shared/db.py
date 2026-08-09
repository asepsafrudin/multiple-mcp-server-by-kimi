"""Async PostgreSQL connection pool helpers."""

from __future__ import annotations

from typing import Any

from psycopg_pool import AsyncConnectionPool

from shared.config import get_settings

_pool: AsyncConnectionPool | None = None


class DatabaseNotConfiguredError(RuntimeError):
    pass


async def get_pool() -> AsyncConnectionPool:
    """Return the global async Postgres pool, creating it on first call."""
    global _pool
    if _pool is None:
        settings = get_settings()
        if not settings.db_url:
            raise DatabaseNotConfiguredError("DB_URL is not set. Add it to your .env file.")
        _pool = AsyncConnectionPool(
            conninfo=settings.db_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            open=False,
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    """Close the global pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def execute(sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params or ())
        await conn.commit()


async def fetchone(
    sql: str, params: tuple[Any, ...] | list[Any] | None = None
) -> tuple[Any, ...] | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params or ())
        return await cur.fetchone()


async def fetchall(
    sql: str, params: tuple[Any, ...] | list[Any] | None = None
) -> list[tuple[Any, ...]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params or ())
        return await cur.fetchall()


async def ensure_vector_extension() -> None:
    """Enable pgvector and install languages if missing."""
    await execute("CREATE EXTENSION IF NOT EXISTS vector;")
