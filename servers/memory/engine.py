"""Memory storage engine backed by SQLite + sqlite-vec + FTS5."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite
import sqlite_vec

from shared.config import get_settings
from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import MemoryEntry

logger = get_logger("mcp.memory.engine")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id                TEXT PRIMARY KEY,
    namespace         TEXT NOT NULL,
    content           TEXT NOT NULL,
    summary           TEXT,
    category          TEXT NOT NULL DEFAULT 'general',
    tags              TEXT DEFAULT '[]',
    importance        INTEGER NOT NULL DEFAULT 5,
    access_count      INTEGER NOT NULL DEFAULT 0,
    quant_level       TEXT NOT NULL DEFAULT 'raw',
    memory_type       TEXT NOT NULL DEFAULT 'semantic',
    validation_status TEXT NOT NULL DEFAULT 'pending',
    source_task_id    TEXT,
    is_archived       INTEGER NOT NULL DEFAULT 0,
    source            TEXT,
    project           TEXT,
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
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    memory_id UNINDEXED,
    namespace UNINDEXED,
    content,
    summary,
    category,
    tags,
    tokenize='trigram'
);
"""

_VEC_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0(
    embedding float[768]
);
"""

_db: aiosqlite.Connection | None = None


@asynccontextmanager
async def _connect():
    """Provide an aiosqlite connection with sqlite-vec loaded."""
    global _db
    settings = get_settings()
    db_path = settings.memory_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if _db is None:
        _db = await aiosqlite.connect(str(db_path), check_same_thread=False)
        await _db.execute("SELECT 1")
        _db._conn.enable_load_extension(True)  # type: ignore[attr-defined]
        sqlite_vec.load(_db._conn)  # type: ignore[arg-type]
        _db._conn.enable_load_extension(False)  # type: ignore[attr-defined]
        _db.row_factory = aiosqlite.Row
    yield _db


async def ensure_memories_table() -> None:
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


def _row_to_entry(row: aiosqlite.Row) -> MemoryEntry:
    tags_raw = row["tags"]
    try:
        tags = json.loads(tags_raw) if tags_raw else []
    except json.JSONDecodeError:
        tags = []
    return MemoryEntry(
        id=row["id"],
        namespace=row["namespace"],
        content=row["content"],
        summary=row["summary"],
        category=row["category"],
        tags=tags,
        importance=row["importance"],
        access_count=row["access_count"],
        quant_level=row["quant_level"],
        memory_type=row["memory_type"],
        validation_status=row["validation_status"],
        source_task_id=row["source_task_id"],
        is_archived=bool(row["is_archived"]),
        source=row["source"],
        project=row["project"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
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
    emb_blob = sqlite_vec.serialize_float32(embedding)

    async with _connect() as db:
        cur = await db.execute(
            """
            INSERT INTO memories
            (id, namespace, content, summary, category, tags, importance,
             access_count, quant_level, memory_type, validation_status, source_task_id,
             is_archived, source, project, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING rowid
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
                entry.created_at or now,
                now,
                entry.expires_at,
            ),
        )
        row = await cur.fetchone()
        rowid = row["rowid"]

        await db.execute(
            """
            INSERT INTO memory_fts(memory_id, namespace, content, summary, category, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.namespace,
                entry.content,
                entry.summary,
                entry.category,
                json.dumps(entry.tags),
            ),
        )
        await db.execute(
            "INSERT INTO memory_vec(rowid, embedding) VALUES (?, ?)",
            (rowid, emb_blob),
        )
        await db.commit()
    return entry.id


async def get_by_id(memory_id: str, namespace: str) -> MemoryEntry | None:
    await ensure_memories_table()
    async with _connect() as db:
        cur = await db.execute(
            """
            SELECT id, namespace, content, summary, category, tags, importance,
                   access_count, quant_level, memory_type, validation_status, source_task_id,
                   is_archived, source, project, created_at, updated_at, expires_at
            FROM memories WHERE id = ? AND namespace = ?
            """,
            (memory_id, namespace),
        )
        row = await cur.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE memories SET access_count = access_count + 1, updated_at = ? WHERE id = ?",
            (_now(), memory_id),
        )
        await db.commit()
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    async with _connect() as db:
        if query_embedding:
            query_blob = sqlite_vec.serialize_float32(query_embedding)
            k_search = max(50, limit * 5)
            sql = """
                SELECT m.*, v.distance AS vector_distance
                FROM memory_vec v
                JOIN memories m ON m.rowid = v.rowid
                WHERE m.namespace = ? AND v.embedding MATCH ? AND k = ?
            """
            params: list[Any] = [namespace, query_blob, k_search]
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            if project:
                sql += " AND m.project = ?"
                params.append(project)
            if min_importance > 1:
                sql += " AND m.importance >= ?"
                params.append(min_importance)
            sql += " ORDER BY v.distance LIMIT ?"
            params.append(limit)

            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            results = []
            ids = []
            for row in rows:
                dist = float(row["vector_distance"])
                # vec0 default metric is L2 distance over normalised vectors.
                # 1.5 ~= cosine similarity > 0.88; keeps results relevant.
                if dist >= 1.5:
                    continue
                entry = _row_to_entry(row)
                results.append(entry)
                ids.append(entry.id)
        else:
            # Fallback to FTS5
            sql = """
                SELECT m.*
                FROM memories m
                JOIN memory_fts f ON f.memory_id = m.id
                WHERE m.namespace = ? AND memory_fts MATCH ?
            """
            params = [namespace, query]
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            if project:
                sql += " AND m.project = ?"
                params.append(project)
            if min_importance > 1:
                sql += " AND m.importance >= ?"
                params.append(min_importance)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            results = [_row_to_entry(r) for r in rows]
            ids = [r.id for r in results]

        if ids:
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE memories SET access_count = access_count + 1, updated_at = ? WHERE id IN ({placeholders})",
                (_now(), *ids),
            )
            await db.commit()
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

    sql = """
        SELECT id, namespace, content, summary, category, tags, importance,
               access_count, quant_level, memory_type, validation_status, source_task_id,
               is_archived, source, project, created_at, updated_at, expires_at
        FROM memories WHERE namespace = ?
    """
    params: list[Any] = [namespace]

    if category:
        sql += " AND category = ?"
        params.append(category)
    if project:
        sql += " AND project = ?"
        params.append(project)
    if since_days:
        cutoff = (datetime.now(UTC) - timedelta(days=since_days)).isoformat()
        sql += " AND created_at >= ?"
        params.append(cutoff)
    if tags:
        for tag in tags:
            sql += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

    sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
    params.append(limit)

    async with _connect() as db:
        cur = await db.execute(sql, params)
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
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    params = list(filtered.values()) + [memory_id, namespace]

    async with _connect() as db:
        cur = await db.execute(
            f"UPDATE memories SET {set_clause} WHERE id = ? AND namespace = ? RETURNING rowid",
            params,
        )
        row = await cur.fetchone()
        if not row:
            return False
        rowid = row["rowid"]

        indexed = {"content", "summary", "category", "tags"}
        if indexed & set(filtered):
            cur2 = await db.execute(
                "SELECT content, summary, category, tags FROM memories WHERE id = ?",
                (memory_id,),
            )
            data = await cur2.fetchone()
            if data:
                tags = json.loads(data["tags"]) if data["tags"] else []
                text = f"{data['category']} | {data['summary'] or data['content']}"
                if tags:
                    text += f" | Tags: {', '.join(tags)}"
                emb = await get_embedding(text)
                await db.execute("DELETE FROM memory_vec WHERE rowid = ?", (rowid,))
                await db.execute(
                    "INSERT INTO memory_vec(rowid, embedding) VALUES (?, ?)",
                    (rowid, sqlite_vec.serialize_float32(emb)),
                )
                await db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
                await db.execute(
                    "INSERT INTO memory_fts(memory_id, namespace, content, summary, category, tags) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        memory_id,
                        namespace,
                        data["content"],
                        data["summary"],
                        data["category"],
                        data["tags"],
                    ),
                )
        await db.commit()
    return True


async def delete(memory_id: str, namespace: str) -> bool:
    await ensure_memories_table()
    async with _connect() as db:
        cur = await db.execute(
            "SELECT rowid FROM memories WHERE id = ? AND namespace = ?",
            (memory_id, namespace),
        )
        row = await cur.fetchone()
        if not row:
            return False
        rowid = row["rowid"]
        await db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
        await db.execute("DELETE FROM memory_vec WHERE rowid = ?", (rowid,))
        await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await db.commit()
    return True


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
    async with _connect() as db:
        cur = await db.execute(
            "SELECT id, rowid FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        rows = await cur.fetchall()
        if rows:
            ids = [r["id"] for r in rows]
            rowids = [r["rowid"] for r in rows]
            id_ph = ",".join("?" for _ in ids)
            rid_ph = ",".join("?" for _ in rowids)
            await db.execute(f"DELETE FROM memory_fts WHERE memory_id IN ({id_ph})", ids)
            await db.execute(f"DELETE FROM memory_vec WHERE rowid IN ({rid_ph})", rowids)
            await db.execute(f"DELETE FROM memories WHERE id IN ({id_ph})", ids)
            await db.commit()
        return len(rows)


async def get_stats(namespace: str | None = None) -> dict[str, Any]:
    await ensure_memories_table()
    async with _connect() as db:
        if namespace:
            cur = await db.execute(
                "SELECT COUNT(*) FROM memories WHERE namespace = ?", (namespace,)
            )
        else:
            cur = await db.execute("SELECT COUNT(*) FROM memories")
        total = (await cur.fetchone())[0]

        if namespace:
            cur = await db.execute(
                "SELECT category, COUNT(*) FROM memories WHERE namespace = ? GROUP BY category",
                (namespace,),
            )
        else:
            cur = await db.execute("SELECT category, COUNT(*) FROM memories GROUP BY category")
        cats = {r[0]: r[1] for r in await cur.fetchall()}

    return {"total_memories": total, "categories": cats, "namespace": namespace}
