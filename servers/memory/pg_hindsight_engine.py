"""Hindsight memory engine for agent learning backed by PostgreSQL + pgvector."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import HindsightExperience, HindsightLearning
from shared.pg_db import get_db_connection

logger = get_logger("mcp.memory.pg_hindsight")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS hindsight_experiences (
    id                TEXT PRIMARY KEY,
    task_description  TEXT NOT NULL,
    action_taken      TEXT NOT NULL,
    outcome           TEXT NOT NULL,
    success           INTEGER NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hindsight_learnings (
    id                TEXT PRIMARY KEY,
    experience_id     TEXT NOT NULL,
    lesson            TEXT NOT NULL,
    advice_for_future TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    embedding         vector(768),
    CONSTRAINT fk_experience
      FOREIGN KEY(experience_id) 
      REFERENCES hindsight_experiences(id) 
      ON DELETE CASCADE
);
"""

async def ensure_db() -> None:
    async with get_db_connection() as conn:
        for stmt in _SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(stmt)
                except Exception as exc:
                    logger.warning("ensure_table_statement_failed", statement=stmt[:60], error=str(exc))
        await conn.commit()

async def store_experience(task_description: str, action_taken: str, outcome: str, success: bool) -> HindsightExperience:
    await ensure_db()
    exp = HindsightExperience(
        id=str(uuid.uuid4()),
        task_description=task_description,
        action_taken=action_taken,
        outcome=outcome,
        success=success
    )
    async with get_db_connection() as conn:
        await conn.execute(
            """INSERT INTO hindsight_experiences (id, task_description, action_taken, outcome, success, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (exp.id, exp.task_description, exp.action_taken, exp.outcome, 1 if exp.success else 0, exp.created_at.isoformat())
        )
        await conn.commit()
    return exp

async def get_experience(exp_id: str) -> HindsightExperience | None:
    await ensure_db()
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM hindsight_experiences WHERE id = %s", (exp_id,))
            row = await cur.fetchone()
            if row:
                return HindsightExperience(
                    id=str(row["id"]),
                    task_description=str(row["task_description"]),
                    action_taken=str(row["action_taken"]),
                    outcome=str(row["outcome"]),
                    success=bool(row["success"])
                )
    return None

async def reflect_and_learn(exp_id: str, lesson: str, advice: str) -> HindsightLearning:
    await ensure_db()
    # Ensure experience exists
    exp = await get_experience(exp_id)
    if not exp:
        raise ValueError(f"Experience {exp_id} not found")
        
    embedding = await get_embedding(advice)
    
    learning = HindsightLearning(
        id=str(uuid.uuid4()),
        experience_id=exp_id,
        lesson=lesson,
        advice_for_future=advice,
        embedding=embedding
    )
    
    async with get_db_connection() as conn:
        await conn.execute(
            """INSERT INTO hindsight_learnings (id, experience_id, lesson, advice_for_future, created_at, embedding)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (learning.id, learning.experience_id, learning.lesson, learning.advice_for_future, learning.created_at.isoformat(), embedding)
        )
        await conn.commit()
    return learning

async def search_advice(current_task: str, limit: int = 3) -> list[HindsightLearning]:
    await ensure_db()
    
    try:
        query_emb = await get_embedding(current_task)
    except Exception as e:
        logger.warning(f"Embedding failed. Cannot perform hindsight search: {e}")
        return []
    
    async with get_db_connection() as conn:
        from psycopg.rows import dict_row
        async with conn.cursor(row_factory=dict_row) as cur:
            sql = """
            SELECT id, experience_id, lesson, advice_for_future, created_at,
                   embedding <-> %s AS distance
            FROM hindsight_learnings
            ORDER BY embedding <-> %s ASC
            LIMIT %s
            """
            await cur.execute(sql, (query_emb, query_emb, limit))
            results = []
            for row in await cur.fetchall():
                results.append(HindsightLearning(
                    id=row["id"],
                    experience_id=row["experience_id"],
                    lesson=row["lesson"],
                    advice_for_future=row["advice_for_future"]
                ))
            return results
