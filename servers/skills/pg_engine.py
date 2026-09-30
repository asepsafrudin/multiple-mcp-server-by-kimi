"""Skill registry engine backed by PostgreSQL + pgvector."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import Skill
from shared.pg_db import get_db_connection

logger = get_logger("mcp.skills.pg_engine")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    namespace       TEXT NOT NULL DEFAULT 'global',
    description     TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    script_path     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    schema          JSONB DEFAULT '{}'::jsonb,
    prompt_template TEXT,
    triggers        JSONB DEFAULT '[]'::jsonb,
    embedding       vector(768),
    fts_vector      tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(description, '') || ' ' || coalesce(prompt_template, '') || ' ' || coalesce(triggers::text, ''))
    ) STORED,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(name, namespace)
);

CREATE INDEX IF NOT EXISTS idx_skills_namespace  ON skills(namespace);
CREATE INDEX IF NOT EXISTS idx_skills_category  ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_name      ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_fts       ON skills USING GIN(fts_vector);
"""

async def ensure_skills_tables() -> None:
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

def _row_to_skill(row: dict) -> Skill:
    def _json(field: str) -> Any:
        v = row.get(field)
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {} if field in {"metadata", "schema"} else []
        return v or ({} if field in {"metadata", "schema"} else [])

    spath = row.get("script_path")
    return Skill(
        id=str(row["id"]),
        name=str(row["name"]),
        namespace=str(row["namespace"]),
        description=str(row["description"]),
        category=str(row["category"]),
        script_path=Path(spath) if spath else None,
        metadata=_json("metadata"),
        schema=_json("schema"),
        prompt_template=str(row["prompt_template"]) if row.get("prompt_template") else None,
        triggers=_json("triggers"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

def _skill_text(skill: Skill) -> str:
    parts = [skill.name, skill.description]
    if skill.category:
        parts.append(f"Category: {skill.category}")
    if skill.triggers:
        parts.append(f"Triggers: {', '.join(skill.triggers)}")
    return " | ".join(parts)

async def register(skill: Skill) -> str:
    """Register or update a skill."""
    await ensure_skills_tables()
    if not skill.id:
        skill.id = str(uuid.uuid4())

    now = _now()
    text = _skill_text(skill)
    try:
        embedding = await get_embedding(text)
    except Exception as exc:
        logger.warning("embedding_failed", error=str(exc))
        embedding = None

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT id FROM skills WHERE name = %s AND namespace = %s", (skill.name, skill.namespace))
            existing = await cur.fetchone()
            
            if existing:
                skill.id = existing["id"]
                await cur.execute(
                    """
                    UPDATE skills SET
                        description = %s, category = %s, script_path = %s,
                        metadata = %s, schema = %s, prompt_template = %s, triggers = %s,
                        embedding = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        skill.description, skill.category, str(skill.script_path) if skill.script_path else None,
                        json.dumps(skill.metadata), json.dumps(skill.schema), skill.prompt_template,
                        json.dumps(skill.triggers), embedding, now, skill.id
                    ),
                )
            else:
                await cur.execute(
                    """
                    INSERT INTO skills
                    (id, name, namespace, description, category, script_path,
                     metadata, schema, prompt_template, triggers, embedding, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        skill.id, skill.name, skill.namespace, skill.description,
                        skill.category, str(skill.script_path) if skill.script_path else None,
                        json.dumps(skill.metadata), json.dumps(skill.schema),
                        skill.prompt_template, json.dumps(skill.triggers),
                        embedding, skill.created_at or now, now
                    ),
                )
        await conn.commit()
    return skill.id

async def load_skill(name: str, namespace: str = "global") -> Skill | None:
    """Load a single skill by name and namespace."""
    await ensure_skills_tables()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM skills WHERE name = %s AND namespace = %s", (name, namespace))
            row = await cur.fetchone()
            if not row:
                return None
            return _row_to_skill(row)

async def list_skills(
    namespace: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List registered skills with optional filters."""
    await ensure_skills_tables()
    sql = "SELECT * FROM skills WHERE 1=1"
    params: list[Any] = []

    if namespace:
        sql += " AND namespace = %s"
        params.append(namespace)
    if category:
        sql += " AND category = %s"
        params.append(category)

    sql += " ORDER BY name LIMIT %s"
    params.append(limit)

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [_skill_to_dict(_row_to_skill(r), None) for r in rows]

async def recall(
    query: str,
    namespace: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Semantic + keyword recall of skills matching the query."""
    await ensure_skills_tables()
    limit = min(limit, 20)

    try:
        query_embedding = await get_embedding(query)
    except Exception as exc:
        logger.warning("embedding_failed", error=str(exc))
        query_embedding = None

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        results = []
        seen_ids = set()

        async with conn.cursor(row_factory=dict_row) as cur:
            if query_embedding:
                sql = """
                    SELECT *, embedding <-> %s AS vector_distance
                    FROM skills
                    WHERE 1=1
                """
                params = [query_embedding]
                if namespace:
                    sql += " AND namespace = %s"
                    params.append(namespace)
                    
                sql += " ORDER BY embedding <-> %s LIMIT %s"
                params.extend([query_embedding, max(50, limit * 5)])

                await cur.execute(sql, params)
                for row in await cur.fetchall():
                    dist = float(row["vector_distance"])
                    if dist >= 1.5:
                        continue
                    skill = _row_to_skill(row)
                    seen_ids.add(skill.id)
                    results.append(_skill_to_dict(skill, dist))
                    if len(results) >= limit:
                        break

            if len(results) < limit:
                remaining = limit - len(results)
                sql = """
                    SELECT *
                    FROM skills
                    WHERE fts_vector @@ plainto_tsquery('simple', %s)
                """
                params = [query]
                if namespace:
                    sql += " AND namespace = %s"
                    params.append(namespace)
                sql += " LIMIT %s"
                params.append(remaining)

                await cur.execute(sql, params)
                for row in await cur.fetchall():
                    skill = _row_to_skill(row)
                    if skill.id in seen_ids:
                        continue
                    seen_ids.add(skill.id)
                    results.append(_skill_to_dict(skill, None))

        return results

def _skill_to_dict(skill: Skill, distance: float | None) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "namespace": skill.namespace,
        "category": skill.category,
        "description": skill.description,
        "script_path": str(skill.script_path) if skill.script_path else None,
        "metadata": skill.metadata,
        "schema": skill.schema,
        "prompt_template": skill.prompt_template[:100] + "..." if skill.prompt_template and len(skill.prompt_template) > 100 else skill.prompt_template,
        "triggers": skill.triggers,
        "distance": distance,
    }

async def update(name: str, namespace: str, updates: dict[str, Any]) -> bool:
    """Update specific fields of an existing skill."""
    await ensure_skills_tables()
    allowed = {
        "description",
        "category",
        "script_path",
        "metadata",
        "schema",
        "prompt_template",
        "triggers",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return False

    if "script_path" in filtered and filtered["script_path"]:
        filtered["script_path"] = str(filtered["script_path"])
    for jfield in ("metadata", "schema", "triggers"):
        if jfield in filtered and not isinstance(filtered[jfield], str):
            filtered[jfield] = json.dumps(filtered[jfield])

    filtered["updated_at"] = _now()
    
    set_keys = list(filtered.keys())
    set_clause = ", ".join(f"{k} = %s" for k in set_keys)
    params = list(filtered.values()) + [name, namespace]

    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"UPDATE skills SET {set_clause} WHERE name = %s AND namespace = %s RETURNING id", params)
            row = await cur.fetchone()
            if not row:
                return False

            indexed = {"description", "category", "triggers"}
            if indexed & set(filtered):
                await cur.execute("SELECT * FROM skills WHERE id = %s", (row["id"],))
                data = await cur.fetchone()
                if data:
                    skill = _row_to_skill(data)
                    new_emb = await get_embedding(_skill_text(skill))
                    await cur.execute("UPDATE skills SET embedding = %s WHERE id = %s", (new_emb, skill.id))
        await conn.commit()
    return True

async def delete_skill(name: str, namespace: str = "global") -> bool:
    """Delete a skill by name and namespace."""
    await ensure_skills_tables()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("DELETE FROM skills WHERE name = %s AND namespace = %s RETURNING id", (name, namespace))
            deleted = await cur.fetchone()
        await conn.commit()
    return bool(deleted)
