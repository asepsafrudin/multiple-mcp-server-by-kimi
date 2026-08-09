"""Skill registry engine backed by SQLite + sqlite-vec + FTS5."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import sqlite_vec

from shared.config import get_settings
from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import Skill

logger = get_logger("mcp.skills.engine")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    namespace       TEXT NOT NULL DEFAULT 'global',
    category        TEXT NOT NULL DEFAULT 'general',
    description     TEXT NOT NULL,
    triggers        TEXT DEFAULT '[]',
    prompt_template TEXT NOT NULL,
    tools_required  TEXT DEFAULT '[]',
    examples        TEXT DEFAULT '[]',
    version         INTEGER NOT NULL DEFAULT 1,
    metadata        TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(namespace, name)
);

CREATE INDEX IF NOT EXISTS idx_skills_namespace  ON skills(namespace);
CREATE INDEX IF NOT EXISTS idx_skills_category  ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_name      ON skills(name);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(
    skill_id UNINDEXED,
    namespace UNINDEXED,
    description,
    triggers,
    prompt_template,
    tokenize='trigram'
);
"""

_VEC_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS skill_vec USING vec0(
    embedding float[768]
);
"""

_db: aiosqlite.Connection | None = None


@asynccontextmanager
async def _connect():
    """Provide an aiosqlite connection with sqlite-vec loaded."""
    global _db  # noqa: PLW0603
    settings = get_settings()
    db_path = Path(settings.memory_db_path).parent / "skills_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if _db is None:
        _db = await aiosqlite.connect(str(db_path), check_same_thread=False)
        await _db.execute("SELECT 1")
        _db._conn.enable_load_extension(True)  # type: ignore[attr-defined]
        sqlite_vec.load(_db._conn)  # type: ignore[arg-type]
        _db._conn.enable_load_extension(False)  # type: ignore[attr-defined]
        _db.row_factory = aiosqlite.Row
    yield _db


async def ensure_skills_tables() -> None:
    async with _connect() as db:
        for stmt in _SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await db.execute(stmt)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ensure_table_statement_failed", statement=stmt[:60], error=str(exc))

        for stmt in (_FTS_SCHEMA.strip(), _VEC_SCHEMA.strip()):
            try:
                await db.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ensure_virtual_table_failed", statement=stmt[:60], error=str(exc))
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_skill(row: aiosqlite.Row) -> Skill:
    def _json(field: str) -> Any:
        raw = row[field]
        try:
            return json.loads(raw) if raw else []
        except json.JSONDecodeError:
            return []

    metadata = {}
    raw_meta = row["metadata"]
    try:
        metadata = json.loads(raw_meta) if raw_meta else {}
    except json.JSONDecodeError:
        metadata = {}

    return Skill(
        id=row["id"],
        name=row["name"],
        namespace=row["namespace"],
        category=row["category"],
        description=row["description"],
        triggers=_json("triggers"),
        prompt_template=row["prompt_template"],
        tools_required=_json("tools_required"),
        examples=_json("examples"),
        version=row["version"],
        embedding=metadata.get("embedding"),
    )


def _skill_text(skill: Skill) -> str:
    text = f"{skill.name}\n{skill.description}\n{skill.prompt_template}"
    if skill.triggers:
        text += "\nTriggers: " + ", ".join(skill.triggers)
    if skill.tools_required:
        text += "\nTools: " + ", ".join(skill.tools_required)
    return text


async def register(skill: Skill) -> str:
    """Register or update a skill."""
    await ensure_skills_tables()
    if not skill.id:
        skill.id = str(uuid.uuid4())

    now = _now()
    embedding = await get_embedding(_skill_text(skill))

    async with _connect() as db:
        # Upsert.
        cur = await db.execute(
            """
            INSERT INTO skills
            (id, name, namespace, category, description, triggers, prompt_template,
             tools_required, examples, version, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, name) DO UPDATE SET
                category=excluded.category,
                description=excluded.description,
                triggers=excluded.triggers,
                prompt_template=excluded.prompt_template,
                tools_required=excluded.tools_required,
                examples=excluded.examples,
                version=excluded.version,
                metadata=excluded.metadata,
                updated_at=excluded.updated_at
            RETURNING rowid
            """,
            (
                skill.id,
                skill.name,
                skill.namespace,
                skill.category,
                skill.description,
                json.dumps(skill.triggers),
                skill.prompt_template,
                json.dumps(skill.tools_required),
                json.dumps(skill.examples),
                skill.version,
                json.dumps({"embedding": embedding}),
                now,
                now,
            ),
        )
        row = await cur.fetchone()
        rowid = row["rowid"]

        await db.execute("DELETE FROM skill_fts WHERE skill_id = ?", (skill.id,))
        await db.execute("DELETE FROM skill_vec WHERE rowid = ?", (rowid,))

        await db.execute(
            "INSERT INTO skill_fts(skill_id, namespace, description, triggers, prompt_template) VALUES (?, ?, ?, ?, ?)",
            (
                skill.id,
                skill.namespace,
                skill.description,
                json.dumps(skill.triggers),
                skill.prompt_template,
            ),
        )
        await db.execute(
            "INSERT INTO skill_vec(rowid, embedding) VALUES (?, ?)",
            (rowid, sqlite_vec.serialize_float32(embedding)),
        )
        await db.commit()

    return skill.id


async def load_skill(name: str, namespace: str = "global") -> Skill | None:
    """Load a single skill by name and namespace."""
    await ensure_skills_tables()
    async with _connect() as db:
        cur = await db.execute(
            "SELECT * FROM skills WHERE namespace = ? AND name = ?",
            (namespace, name),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return _row_to_skill(row)


async def list_skills(
    namespace: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[Skill]:
    """List registered skills with optional filters."""
    await ensure_skills_tables()
    if limit > 200:
        limit = 200

    sql = "SELECT * FROM skills WHERE 1=1"
    params: list[Any] = []
    if namespace:
        sql += " AND namespace = ?"
        params.append(namespace)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY namespace, name LIMIT ?"
    params.append(limit)

    async with _connect() as db:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [_row_to_skill(r) for r in rows]


async def recall(
    query: str,
    namespace: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Semantic + keyword recall of skills matching the query."""
    await ensure_skills_tables()
    if limit > 20:
        limit = 20

    try:
        query_embedding = await get_embedding(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    async with _connect() as db:
        if query_embedding:
            query_blob = sqlite_vec.serialize_float32(query_embedding)
            k_search = max(50, limit * 5)
            sql = """
                SELECT s.*, v.distance AS vector_distance
                FROM skill_vec v
                JOIN skills s ON s.rowid = v.rowid
                WHERE v.embedding MATCH ? AND k = ?
            """
            params: list[Any] = [query_blob, k_search]
            if namespace:
                sql += " AND s.namespace = ?"
                params.append(namespace)
            sql += " ORDER BY v.distance LIMIT ?"
            params.append(limit)

            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            for row in rows:
                dist = float(row["vector_distance"])
                if dist >= 1.5:
                    continue
                skill = _row_to_skill(row)
                seen_ids.add(skill.id)
                results.append(_skill_to_dict(skill, dist))

        if len(results) < limit:
            remaining = limit - len(results)
            sql = """
                SELECT s.*
                FROM skills s
                JOIN skill_fts f ON f.skill_id = s.id
                WHERE skill_fts MATCH ?
            """
            params = [query]
            if namespace:
                sql += " AND s.namespace = ?"
                params.append(namespace)
            sql += " ORDER BY rank LIMIT ?"
            params.append(remaining)

            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            for row in rows:
                skill = _row_to_skill(row)
                if skill.id in seen_ids:
                    continue
                seen_ids.add(skill.id)
                results.append(_skill_to_dict(skill, None))

    if not results:
        return [{"status": "no_results", "message": f"No skills match: '{query}'"}]
    return results


def _skill_to_dict(skill: Skill, distance: float | None) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "namespace": skill.namespace,
        "category": skill.category,
        "description": skill.description,
        "triggers": skill.triggers,
        "prompt_template": skill.prompt_template,
        "tools_required": skill.tools_required,
        "examples": skill.examples,
        "version": skill.version,
        "distance": distance,
    }


async def update(name: str, namespace: str, updates: dict[str, Any]) -> bool:
    """Update specific fields of an existing skill."""
    await ensure_skills_tables()
    allowed = {
        "category", "description", "triggers", "prompt_template",
        "tools_required", "examples", "version",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return False

    for key in ("triggers", "tools_required", "examples"):
        if key in filtered and isinstance(filtered[key], list):
            filtered[key] = json.dumps(filtered[key])

    filtered["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    params = list(filtered.values()) + [name, namespace]

    async with _connect() as db:
        cur = await db.execute(
            f"UPDATE skills SET {set_clause} WHERE name = ? AND namespace = ? RETURNING id, rowid",  # noqa: S608
            params,
        )
        row = await cur.fetchone()
        if not row:
            return False
        skill_id = row["id"]
        rowid = row["rowid"]

        # Rebuild embedding + index.
        cur2 = await db.execute(
            "SELECT * FROM skills WHERE id = ?",
            (skill_id,),
        )
        skill = _row_to_skill(await cur2.fetchone())
        embedding = await get_embedding(_skill_text(skill))

        await db.execute("DELETE FROM skill_vec WHERE rowid = ?", (rowid,))
        await db.execute(
            "INSERT INTO skill_vec(rowid, embedding) VALUES (?, ?)",
            (rowid, sqlite_vec.serialize_float32(embedding)),
        )
        await db.execute(
            "UPDATE skills SET metadata = ? WHERE id = ?",
            (json.dumps({"embedding": embedding}), skill_id),
        )
        await db.commit()
    return True


async def delete_skill(name: str, namespace: str = "global") -> bool:
    """Delete a skill by name and namespace."""
    await ensure_skills_tables()
    async with _connect() as db:
        cur = await db.execute(
            "SELECT id, rowid FROM skills WHERE name = ? AND namespace = ?",
            (name, namespace),
        )
        row = await cur.fetchone()
        if not row:
            return False
        skill_id = row["id"]
        rowid = row["rowid"]
        await db.execute("DELETE FROM skill_fts WHERE skill_id = ?", (skill_id,))
        await db.execute("DELETE FROM skill_vec WHERE rowid = ?", (rowid,))
        await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        await db.commit()
    return True
