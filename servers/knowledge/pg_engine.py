"""Knowledge storage engine backed by PostgreSQL + pgvector + Native FTS."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from shared.embeddings import get_embeddings
from shared.logging import get_logger
from shared.models import KnowledgeChunk
from shared.pg_db import get_db_connection

logger = get_logger("mcp.knowledge.pg_engine")

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
    metadata     JSONB DEFAULT '{}'::jsonb,
    embedding    vector(768),
    fts_vector   tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(project, '') || ' ' || coalesce(content, ''))) STORED,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_project   ON knowledge_chunks(project);
CREATE INDEX IF NOT EXISTS idx_knowledge_file_path ON knowledge_chunks(file_path);
CREATE INDEX IF NOT EXISTS idx_knowledge_file_hash ON knowledge_chunks(file_hash);
CREATE INDEX IF NOT EXISTS idx_knowledge_fts ON knowledge_chunks USING GIN (fts_vector);
"""

async def ensure_knowledge_tables() -> None:
    async with get_db_connection() as conn:
        for stmt in _SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(stmt)
                except Exception as exc:
                    logger.warning("ensure_table_statement_failed", statement=stmt[:60], error=str(exc))
        await conn.commit()

def _now() -> str:
    return datetime.now(UTC).isoformat()

def _row_to_chunk(row: dict) -> KnowledgeChunk:
    metadata_raw = row["metadata"]
    if isinstance(metadata_raw, str):
        try:
            metadata = json.loads(metadata_raw)
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = metadata_raw or {}
        
    return KnowledgeChunk(
        id=str(row["id"]),
        project=str(row["project"]),
        file_path=str(row["file_path"]),
        file_hash=str(row["file_hash"]),
        file_type=str(row["file_type"]),
        chunk_index=int(row["chunk_index"]),
        total_chunks=int(row["total_chunks"]),
        content=str(row["content"]),
        metadata=metadata,
    )

async def index_chunks(chunks: list[KnowledgeChunk]) -> dict[str, Any]:
    """Upsert knowledge chunks with embeddings."""
    await ensure_knowledge_tables()
    if not chunks:
        return {"indexed": 0, "project": None}

    project = chunks[0].project
    now = _now()

    for chunk in chunks:
        if not chunk.id:
            chunk.id = str(uuid.uuid4())

    texts = [f"{chunk.project} | {chunk.file_path} | {chunk.content}" for chunk in chunks]
    try:
        embeddings = await get_embeddings(texts)
    except Exception as exc:
        logger.error("embedding_failed", error=str(exc))
        return {"indexed": 0, "project": project, "error": str(exc)}

    file_paths = list({c.file_path for c in chunks})

    async with get_db_connection() as conn:
        # Hapus chunk usang menggunakan postgres-native query (UNNEST)
        await conn.execute(
            "DELETE FROM knowledge_chunks WHERE project = %s AND file_path = ANY(%s)",
            (project, file_paths)
        )

        inserted = 0
        
        # Batch insert
        for chunk, embedding in zip(chunks, embeddings):
            meta_json = json.dumps(chunk.metadata)
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                (id, project, file_path, file_hash, file_type, chunk_index, total_chunks,
                 content, metadata, embedding, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    meta_json,
                    embedding,  # psycopg dengan pgvector me-*register* otomatis tipe float list!
                    now,
                    now,
                ),
            )
            inserted += 1

        await conn.commit()

    return {"indexed": inserted, "project": project}


async def search(
    query: str,
    project: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid semantic (pgvector L2) + keyword (tsvector) search over knowledge chunks."""
    await ensure_knowledge_tables()
    limit = min(limit, 20)

    from shared.embeddings import get_embedding

    try:
        query_embedding = await get_embedding(query)
    except Exception as exc:
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    async with get_db_connection() as conn:
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Semantic Search dengan pgvector (<-> adalah Euclidean L2 distance)
        if query_embedding:
            k_search = max(50, limit * 5)
            sql = """
                SELECT *, embedding <-> %s AS vector_distance
                FROM knowledge_chunks
                WHERE 1=1
            """
            params = [query_embedding]
            if project:
                sql += " AND project = %s"
                params.append(project)
                
            sql += " ORDER BY embedding <-> %s LIMIT %s"
            params.extend([query_embedding, k_search])

            from psycopg.rows import dict_row
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
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
                
                # Batasi sesuai limit yg diminta jika semantic sudah cukup
                if len(results) >= limit:
                    break

        # Fallback / supplement dengan Native PostgreSQL TSVector
        if len(results) < limit:
            remaining = limit - len(results)
            sql = """
                SELECT *
                FROM knowledge_chunks
                WHERE fts_vector @@ plainto_tsquery('simple', %s)
            """
            params = [query]
            if project:
                sql += " AND project = %s"
                params.append(project)
                
            sql += " LIMIT %s"
            params.append(remaining)

            from psycopg.rows import dict_row
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
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
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("DELETE FROM knowledge_chunks WHERE project = %s RETURNING id", (project,))
            deleted_rows = await cur.fetchall()
        await conn.commit()

    return {"deleted_project": project, "chunks_removed": len(deleted_rows)}


async def get_stats(project: str | None = None) -> dict[str, Any]:
    """Return knowledge statistics."""
    await ensure_knowledge_tables()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            if project:
                await cur.execute("SELECT COUNT(*) AS c FROM knowledge_chunks WHERE project = %s", (project,))
                total = (await cur.fetchone())["c"]
                await cur.execute("SELECT file_type, COUNT(*) AS c FROM knowledge_chunks WHERE project = %s GROUP BY file_type", (project,))
            else:
                await cur.execute("SELECT COUNT(*) AS c FROM knowledge_chunks")
                total = (await cur.fetchone())["c"]
                await cur.execute("SELECT file_type, COUNT(*) AS c FROM knowledge_chunks GROUP BY file_type")
            
            types = {r["file_type"]: r["c"] for r in await cur.fetchall()}

            if project:
                await cur.execute("SELECT COUNT(DISTINCT file_path) AS c FROM knowledge_chunks WHERE project = %s", (project,))
            else:
                await cur.execute("SELECT COUNT(DISTINCT file_path) AS c FROM knowledge_chunks")
            files = (await cur.fetchone())["c"]

    return {
        "total_chunks": total,
        "unique_files": files,
        "file_types": types,
        "project": project,
    }
