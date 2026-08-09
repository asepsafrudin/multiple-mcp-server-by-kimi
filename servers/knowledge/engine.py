"""Knowledge storage engine backed by SQLite + sqlite-vec + FTS5."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import sqlite_vec

from shared.config import get_settings
from shared.embeddings import get_embeddings
from shared.logging import get_logger
from shared.models import KnowledgeChunk

logger = get_logger("mcp.knowledge.engine")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id           TEXT PRIMARY KEY,
    project      TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    file_hash    TEXT NOT NULL,
    file_type    TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    content      TEXT NOT NULL,
    metadata     TEXT DEFAULT '{}',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_project   ON knowledge_chunks(project);
CREATE INDEX IF NOT EXISTS idx_knowledge_file_path ON knowledge_chunks(file_path);
CREATE INDEX IF NOT EXISTS idx_knowledge_file_hash ON knowledge_chunks(file_hash);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    chunk_id UNINDEXED,
    project UNINDEXED,
    content,
    tokenize='trigram'
);
"""

_VEC_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_vec USING vec0(
    embedding float[768]
);
"""

_db: aiosqlite.Connection | None = None


@asynccontextmanager
async def _connect():
    """Provide an aiosqlite connection with sqlite-vec loaded."""
    global _db
    settings = get_settings()
    db_path = settings.knowledge_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if _db is None:
        _db = await aiosqlite.connect(str(db_path), check_same_thread=False)
        await _db.execute("SELECT 1")
        _db._conn.enable_load_extension(True)  # type: ignore[attr-defined]
        sqlite_vec.load(_db._conn)  # type: ignore[arg-type]
        _db._conn.enable_load_extension(False)  # type: ignore[attr-defined]
        _db.row_factory = aiosqlite.Row
    yield _db


async def ensure_knowledge_tables() -> None:
    async with _connect() as db:
        for stmt in _SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await db.execute(stmt)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "ensure_table_statement_failed", statement=stmt[:60], error=str(exc)
                    )

        for stmt in (_FTS_SCHEMA.strip(), _VEC_SCHEMA.strip()):
            try:
                await db.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ensure_virtual_table_failed", statement=stmt[:60], error=str(exc))
        await db.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_chunk(row: aiosqlite.Row) -> KnowledgeChunk:
    metadata_raw = row["metadata"]
    try:
        metadata = json.loads(metadata_raw) if metadata_raw else {}
    except json.JSONDecodeError:
        metadata = {}
    return KnowledgeChunk(
        id=row["id"],
        project=row["project"],
        file_path=row["file_path"],
        file_hash=row["file_hash"],
        file_type=row["file_type"],
        chunk_index=row["chunk_index"],
        total_chunks=row["total_chunks"],
        content=row["content"],
        metadata=metadata,
    )


async def index_chunks(chunks: list[KnowledgeChunk]) -> dict[str, Any]:
    """Upsert knowledge chunks with embeddings.

    Existing chunks for the same (project, file_path) are replaced so re-indexing
    stays idempotent.
    """
    await ensure_knowledge_tables()
    if not chunks:
        return {"indexed": 0, "project": None}

    project = chunks[0].project
    now = _now()

    # Assign IDs and gather text for embedding.
    for chunk in chunks:
        if not chunk.id:
            chunk.id = str(uuid.uuid4())

    texts = [f"{chunk.project} | {chunk.file_path} | {chunk.content}" for chunk in chunks]
    try:
        embeddings = await get_embeddings(texts)
    except Exception as exc:  # noqa: BLE001
        logger.error("embedding_failed", error=str(exc))
        return {"indexed": 0, "project": project, "error": str(exc)}

    file_paths = list({c.file_path for c in chunks})

    async with _connect() as db:
        # Delete stale chunks for the affected files first.
        placeholders = ",".join("?" for _ in file_paths)
        cur = await db.execute(
            f"SELECT id, rowid FROM knowledge_chunks WHERE project = ? AND file_path IN ({placeholders})",
            (project, *file_paths),
        )
        stale_rows = await cur.fetchall()
        stale_ids = [r["id"] for r in stale_rows]
        stale_rowids = [r["rowid"] for r in stale_rows]

        if stale_ids:
            id_ph = ",".join("?" for _ in stale_ids)
            await db.execute(
                f"DELETE FROM knowledge_fts WHERE chunk_id IN ({id_ph})",
                stale_ids,
            )
        if stale_rowids:
            rid_ph = ",".join("?" for _ in stale_rowids)
            await db.execute(
                f"DELETE FROM knowledge_vec WHERE rowid IN ({rid_ph})",
                stale_rowids,
            )
        await db.execute(
            f"DELETE FROM knowledge_chunks WHERE project = ? AND file_path IN ({placeholders})",
            (project, *file_paths),
        )

        inserted = 0
        for chunk, embedding in zip(chunks, embeddings):
            cur = await db.execute(
                """
                INSERT INTO knowledge_chunks
                (id, project, file_path, file_hash, file_type, chunk_index, total_chunks,
                 content, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING rowid
                """,
                (
                    chunk.id,
                    chunk.project,
                    chunk.file_path,
                    chunk.file_hash,
                    chunk.file_type,
                    chunk.chunk_index,
                    chunk.total_chunks,
                    chunk.content,
                    json.dumps(chunk.metadata),
                    now,
                    now,
                ),
            )
            row = await cur.fetchone()
            rowid = row["rowid"]

            await db.execute(
                "INSERT INTO knowledge_fts(chunk_id, project, content) VALUES (?, ?, ?)",
                (chunk.id, chunk.project, chunk.content),
            )
            await db.execute(
                "INSERT INTO knowledge_vec(rowid, embedding) VALUES (?, ?)",
                (rowid, sqlite_vec.serialize_float32(embedding)),
            )
            inserted += 1

        await db.commit()

    return {"indexed": inserted, "project": project}


async def search(
    query: str,
    project: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid semantic + keyword search over knowledge chunks."""
    await ensure_knowledge_tables()
    limit = min(limit, 20)

    from shared.embeddings import get_embedding

    try:
        query_embedding = await get_embedding(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    async with _connect() as db:
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        if query_embedding:
            query_blob = sqlite_vec.serialize_float32(query_embedding)
            k_search = max(50, limit * 5)
            sql = """
                SELECT c.*, v.distance AS vector_distance
                FROM knowledge_vec v
                JOIN knowledge_chunks c ON c.rowid = v.rowid
                WHERE v.embedding MATCH ? AND k = ?
            """
            params: list[Any] = [query_blob, k_search]
            if project:
                sql += " AND c.project = ?"
                params.append(project)
            sql += " ORDER BY v.distance LIMIT ?"
            params.append(limit)

            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            for row in rows:
                dist = float(row["vector_distance"])
                if dist >= 1.5:
                    continue
                chunk = _row_to_chunk(row)
                seen_ids.add(chunk.id)
                results.append(
                    {
                        "id": chunk.id,
                        "project": chunk.project,
                        "file_path": chunk.file_path,
                        "file_type": chunk.file_type,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                        "content": chunk.content[:800],
                        "metadata": chunk.metadata,
                        "distance": dist,
                    }
                )

        # Fallback / supplement with FTS5.
        if len(results) < limit:
            remaining = limit - len(results)
            sql = """
                SELECT c.*
                FROM knowledge_chunks c
                JOIN knowledge_fts f ON f.chunk_id = c.id
                WHERE knowledge_fts MATCH ?
            """
            params = [query]
            if project:
                sql += " AND c.project = ?"
                params.append(project)
            sql += " ORDER BY rank LIMIT ?"
            params.append(remaining)

            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            for row in rows:
                chunk = _row_to_chunk(row)
                if chunk.id in seen_ids:
                    continue
                seen_ids.add(chunk.id)
                results.append(
                    {
                        "id": chunk.id,
                        "project": chunk.project,
                        "file_path": chunk.file_path,
                        "file_type": chunk.file_type,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                        "content": chunk.content[:800],
                        "metadata": chunk.metadata,
                        "distance": None,
                    }
                )

        if not results:
            return [{"status": "no_results", "message": f"No knowledge matches: '{query}'"}]
        return results


async def delete_project(project: str) -> dict[str, Any]:
    """Delete all chunks belonging to a project."""
    await ensure_knowledge_tables()
    async with _connect() as db:
        cur = await db.execute(
            "SELECT rowid FROM knowledge_chunks WHERE project = ?",
            (project,),
        )
        rowids = [r["rowid"] for r in await cur.fetchall()]

        await db.execute("DELETE FROM knowledge_fts WHERE project = ?", (project,))
        if rowids:
            placeholders = ",".join("?" for _ in rowids)
            await db.execute(
                f"DELETE FROM knowledge_vec WHERE rowid IN ({placeholders})",
                rowids,
            )
        await db.execute("DELETE FROM knowledge_chunks WHERE project = ?", (project,))
        await db.commit()

    return {"deleted_project": project, "chunks_removed": len(rowids)}


async def get_stats(project: str | None = None) -> dict[str, Any]:
    """Return knowledge statistics."""
    await ensure_knowledge_tables()
    async with _connect() as db:
        if project:
            cur = await db.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE project = ?",
                (project,),
            )
            total = (await cur.fetchone())[0]
            cur = await db.execute(
                "SELECT file_type, COUNT(*) FROM knowledge_chunks WHERE project = ? GROUP BY file_type",
                (project,),
            )
        else:
            cur = await db.execute("SELECT COUNT(*) FROM knowledge_chunks")
            total = (await cur.fetchone())[0]
            cur = await db.execute(
                "SELECT file_type, COUNT(*) FROM knowledge_chunks GROUP BY file_type"
            )
        types = {r[0]: r[1] for r in await cur.fetchall()}

        if project:
            cur = await db.execute(
                "SELECT COUNT(DISTINCT file_path) FROM knowledge_chunks WHERE project = ?",
                (project,),
            )
        else:
            cur = await db.execute("SELECT COUNT(DISTINCT file_path) FROM knowledge_chunks")
        files = (await cur.fetchone())[0]

    return {
        "total_chunks": total,
        "unique_files": files,
        "file_types": types,
        "project": project,
    }
