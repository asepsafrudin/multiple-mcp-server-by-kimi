"""Memory storage engine backed by PostgreSQL + pgvector + Native FTS."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import MemoryEntry
from shared.pg_db import get_db_connection

logger = get_logger("mcp.memory.pg_engine")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id                TEXT PRIMARY KEY,
    namespace         TEXT NOT NULL,
    content           TEXT NOT NULL,
    summary           TEXT,
    category          TEXT NOT NULL DEFAULT 'general',
    tags              JSONB DEFAULT '[]'::jsonb,
    importance        INTEGER NOT NULL DEFAULT 5,
    access_count      INTEGER NOT NULL DEFAULT 0,
    quant_level       TEXT NOT NULL DEFAULT 'raw',
    memory_type       TEXT NOT NULL DEFAULT 'semantic',
    validation_status TEXT NOT NULL DEFAULT 'pending',
    source_task_id    TEXT,
    is_archived       INTEGER NOT NULL DEFAULT 0,
    source            TEXT,
    project           TEXT,
    embedding         vector(768),
    fts_vector        tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(content, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(category, '') || ' ' || coalesce(tags::text, ''))
    ) STORED,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    expires_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_memories_namespace  ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_category   ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_project    ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created    ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_expires    ON memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_memories_fts        ON memories USING GIN(fts_vector);
"""

async def ensure_memories_table() -> None:
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

def _row_to_entry(row: dict) -> MemoryEntry:
    tags_raw = row["tags"]
    if isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []
    else:
        tags = tags_raw or []
        
    return MemoryEntry(
        id=str(row["id"]),
        namespace=str(row["namespace"]),
        content=str(row["content"]),
        summary=str(row["summary"]) if row.get("summary") else None,
        category=str(row["category"]),
        tags=tags,
        importance=int(row["importance"]),
        access_count=int(row["access_count"]),
        quant_level=str(row["quant_level"]),
        memory_type=str(row["memory_type"]),
        validation_status=str(row["validation_status"]),
        source_task_id=str(row["source_task_id"]) if row.get("source_task_id") else None,
        is_archived=bool(row["is_archived"]),
        source=str(row["source"]) if row.get("source") else None,
        project=str(row["project"]) if row.get("project") else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        expires_at=str(row["expires_at"]) if row.get("expires_at") else None,
    )

def _text_to_embed(entry: MemoryEntry) -> str:
    text = f"{entry.category} | {entry.summary or entry.content}"
    if entry.tags:
        text += f" | Tags: {', '.join(entry.tags)}"
    return text

async def store(entry: MemoryEntry) -> str:
    await ensure_memories_table()
    if not entry.id:
        entry.id = str(uuid.uuid4())

    now = _now()
    embedding = await get_embedding(_text_to_embed(entry))

    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO memories
            (id, namespace, content, summary, category, tags, importance,
             access_count, quant_level, memory_type, validation_status, source_task_id,
             is_archived, source, project, embedding, created_at, updated_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.id,
                entry.namespace,
                entry.content,
                entry.summary,
                entry.category,
                json.dumps(entry.tags),
                entry.importance,
                entry.access_count,
                entry.quant_level,
                entry.memory_type,
                entry.validation_status,
                entry.source_task_id,
                int(entry.is_archived),
                entry.source,
                entry.project,
                embedding,
                entry.created_at or now,
                now,
                entry.expires_at,
            ),
        )
        await conn.commit()
    return entry.id

async def get_by_id(memory_id: str, namespace: str) -> MemoryEntry | None:
    await ensure_memories_table()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, namespace, content, summary, category, tags, importance,
                       access_count, quant_level, memory_type, validation_status, source_task_id,
                       is_archived, source, project, created_at, updated_at, expires_at
                FROM memories WHERE id = %s AND namespace = %s
                """,
                (memory_id, namespace),
            )
            row = await cur.fetchone()
            if not row:
                return None
            await cur.execute(
                "UPDATE memories SET access_count = access_count + 1, updated_at = %s WHERE id = %s",
                (_now(), memory_id),
            )
        await conn.commit()
        return _row_to_entry(row)

async def recall(
    query: str,
    namespace: str,
    limit: int = 5,
    category: str | None = None,
    project: str | None = None,
    min_importance: int = 1,
) -> list[MemoryEntry]:
    await ensure_memories_table()
    limit = min(limit, 20)

    try:
        query_embedding = await get_embedding(query)
    except Exception as exc:
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        results = []
        ids = []

        async with conn.cursor(row_factory=dict_row) as cur:
            if query_embedding:
                k_search = max(50, limit * 5)
                sql = """
                    SELECT *, embedding <-> %s AS vector_distance
                    FROM memories
                    WHERE namespace = %s
                """
                params = [query_embedding, namespace]
                if category:
                    sql += " AND category = %s"
                    params.append(category)
                if project:
                    sql += " AND project = %s"
                    params.append(project)
                if min_importance > 1:
                    sql += " AND importance >= %s"
                    params.append(min_importance)
                
                sql += " ORDER BY embedding <-> %s LIMIT %s"
                params.extend([query_embedding, limit])

                await cur.execute(sql, params)
                rows = await cur.fetchall()
                for row in rows:
                    dist = float(row["vector_distance"])
                    if dist >= 1.5:
                        continue
                    entry = _row_to_entry(row)
                    results.append(entry)
                    ids.append(entry.id)
            else:
                # Fallback ke FTS
                sql = """
                    SELECT *
                    FROM memories
                    WHERE namespace = %s AND fts_vector @@ plainto_tsquery('simple', %s)
                """
                params = [namespace, query]
                if category:
                    sql += " AND category = %s"
                    params.append(category)
                if project:
                    sql += " AND project = %s"
                    params.append(project)
                if min_importance > 1:
                    sql += " AND importance >= %s"
                    params.append(min_importance)
                sql += " LIMIT %s"
                params.append(limit)

                await cur.execute(sql, params)
                rows = await cur.fetchall()
                for row in rows:
                    entry = _row_to_entry(row)
                    results.append(entry)
                    ids.append(entry.id)

            if ids:
                await cur.execute(
                    "UPDATE memories SET access_count = access_count + 1, updated_at = %s WHERE id = ANY(%s)",
                    (_now(), ids),
                )
        await conn.commit()
        return results

async def search_by_filters(
    namespace: str,
    tags: list[str] | None = None,
    category: str | None = None,
    project: str | None = None,
    since_days: int | None = None,
    limit: int = 10,
) -> list[MemoryEntry]:
    await ensure_memories_table()
    limit = min(limit, 50)

    sql = "SELECT * FROM memories WHERE namespace = %s"
    params: list[Any] = [namespace]

    if category:
        sql += " AND category = %s"
        params.append(category)
    if project:
        sql += " AND project = %s"
        params.append(project)
    if since_days:
        cutoff = (datetime.now(UTC) - timedelta(days=since_days)).isoformat()
        sql += " AND created_at >= %s"
        params.append(cutoff)
    if tags:
        for tag in tags:
            sql += " AND tags @> %s::jsonb"
            params.append(json.dumps([tag]))

    sql += " ORDER BY importance DESC, created_at DESC LIMIT %s"
    params.append(limit)

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [_row_to_entry(r) for r in rows]

async def update(memory_id: str, namespace: str, updates: dict[str, Any]) -> bool:
    await ensure_memories_table()
    allowed = {
        "content",
        "summary",
        "category",
        "tags",
        "importance",
        "quant_level",
        "memory_type",
        "validation_status",
        "source_task_id",
        "is_archived",
        "source",
        "project",
        "expires_at",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return False

    if "tags" in filtered and isinstance(filtered["tags"], list):
        filtered["tags"] = json.dumps(filtered["tags"])

    filtered["updated_at"] = _now()
    set_keys = list(filtered.keys())
    set_clause = ", ".join(f"{k} = %s" for k in set_keys)
    params = list(filtered.values()) + [memory_id, namespace]

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"UPDATE memories SET {set_clause} WHERE id = %s AND namespace = %s RETURNING id",
                params,
            )
            row = await cur.fetchone()
            if not row:
                return False

            indexed = {"content", "summary", "category", "tags"}
            if indexed & set(filtered):
                await cur.execute(
                    "SELECT content, summary, category, tags FROM memories WHERE id = %s",
                    (memory_id,),
                )
                data = await cur.fetchone()
                if data:
                    tags = json.loads(data["tags"]) if isinstance(data["tags"], str) else (data["tags"] or [])
                    text = f"{data['category']} | {data['summary'] or data['content']}"
                    if tags:
                        text += f" | Tags: {', '.join(tags)}"
                    emb = await get_embedding(text)
                    await cur.execute("UPDATE memories SET embedding = %s WHERE id = %s", (emb, memory_id))
        await conn.commit()
    return True

async def delete(memory_id: str, namespace: str) -> bool:
    await ensure_memories_table()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("DELETE FROM memories WHERE id = %s AND namespace = %s RETURNING id", (memory_id, namespace))
            deleted = await cur.fetchone()
        await conn.commit()
    return bool(deleted)

async def quantize(memory_id: str, namespace: str, level: str) -> bool:
    entry = await get_by_id(memory_id, namespace)
    if not entry:
        return False

    if level == "summary":
        summary = entry.summary or entry.content[:300]
        if len(entry.content) > 300:
            summary += "..."
        await update(memory_id, namespace, {"summary": summary, "quant_level": "summary"})
        return True

    if level == "compressed":
        compressed = {
            "category": entry.category,
            "tags": entry.tags,
            "key_content": (entry.summary or entry.content)[:150],
            "importance": entry.importance,
        }
        await update(
            memory_id,
            namespace,
            {
                "summary": json.dumps(compressed, ensure_ascii=False),
                "content": (entry.summary or entry.content)[:150],
                "quant_level": "compressed",
            },
        )
        return True

    return False

async def cleanup_expired() -> int:
    await ensure_memories_table()
    now = _now()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < %s RETURNING id",
                (now,),
            )
            rows = await cur.fetchall()
        await conn.commit()
        return len(rows)

async def get_stats(namespace: str | None = None) -> dict[str, Any]:
    await ensure_memories_table()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            if namespace:
                await cur.execute("SELECT COUNT(*) AS c FROM memories WHERE namespace = %s", (namespace,))
                total = (await cur.fetchone())["c"]
                await cur.execute(
                    "SELECT category, COUNT(*) AS c FROM memories WHERE namespace = %s GROUP BY category",
                    (namespace,),
                )
            else:
                await cur.execute("SELECT COUNT(*) AS c FROM memories")
                total = (await cur.fetchone())["c"]
                await cur.execute("SELECT category, COUNT(*) AS c FROM memories GROUP BY category")
            cats = {r["category"]: r["c"] for r in await cur.fetchall()}

    return {"total_memories": total, "categories": cats, "namespace": namespace}
