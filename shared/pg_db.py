"""PostgreSQL connection pool management untuk migrasi MCP.

Menyediakan Singleton Connection Pool yang aman secara konkurensi,
dan mendaftarkan extension pgvector (vector serialization PostgreSQL)
pada setiap koneksi yang baru diciptakan.
"""

from __future__ import annotations

import contextlib
from typing import AsyncGenerator

from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger("mcp.pg_db")


class PgDatabase:
    """Manages the PostgreSQL connection pool lifecycle."""

    def __init__(self) -> None:
        self._pool: AsyncConnectionPool | None = None

    async def initialize(self) -> None:
        """Create the connection pool if it doesn't exist."""
        if self._pool is not None:
            return

        settings = get_settings()
        if not settings.db_url:
            raise RuntimeError("Kredensial DB_URL tidak ditemukan. Pastikan sudah terset di .env")

        url = settings.db_url
        # psycopg-pool dan psycopg3 mengharapkan prefix 'postgresql://' bukan asyncpg
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://")

        async def configure_connection(conn) -> None:
            """Hook ini berjalan 1x saat koneksi baru di-spawn di dalam pool."""
            # Mendaftarkan tipe 'vector' (pgvector) sehingga kita bisa lempar Python List/Numpy langsung
            await register_vector_async(conn)

        # Inisiasi AsyncPool
        self._pool = AsyncConnectionPool(
            conninfo=url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            kwargs={"autocommit": False},
            configure=configure_connection,
            open=False,  # Buka secara asinkron di bawah
        )
        await self._pool.open()
        await self._pool.wait()
        
        # Sembunyikan credential password di log
        safe_url = url.split("@")[-1] if "@" in url else url
        logger.info("postgres_pool_initialized", target=safe_url)

    async def get_connection(self) -> AsyncGenerator:
        """Yield a connection dari dalam pool."""
        if self._pool is None:
            await self.initialize()

        async with self._pool.connection() as conn:  # type: ignore
            yield conn

    async def close(self) -> None:
        """Hentikan pool dan semua koneksinya."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("postgres_pool_closed")


# Singleton connection manager
_db = PgDatabase()


@contextlib.asynccontextmanager
async def get_db_connection() -> AsyncGenerator:
    """Context manager global untuk mendapatkan koneksi PostgreSQL."""
    async for conn in _db.get_connection():
        yield conn


async def init_pg_db() -> None:
    """Inisialisasi pool PostgreSQL (biasanya dipanggil di lifespan FastMCP)."""
    await _db.initialize()


async def close_pg_db() -> None:
    """Shutdown pool PostgreSQL secara anggun."""
    await _db.close()
