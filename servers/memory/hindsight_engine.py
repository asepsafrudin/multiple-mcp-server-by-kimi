"""Hindsight memory engine for agent learning (SQLite + sqlite-vec)."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
import sqlite_vec

from shared.config import get_settings
from shared.embeddings import get_embedding
from shared.logging import get_logger
from shared.models import HindsightExperience, HindsightLearning

logger = get_logger("mcp.memory.hindsight")

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
    FOREIGN KEY(experience_id) REFERENCES hindsight_experiences(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS hindsight_vec USING vec0(
    learning_id TEXT PRIMARY KEY,
    embedding FLOAT[1536]
);
"""

_db = None

@asynccontextmanager
async def _connect():
    global _db
    settings = get_settings()
    db_path = settings.hindsight_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    if _db is None:
        _db = await aiosqlite.connect(str(db_path), check_same_thread=False)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA foreign_keys = ON;")
        
        # Load extensions directly on core connection
        _db._conn.enable_load_extension(True)
        sqlite_vec.load(_db._conn)
        _db._conn.enable_load_extension(False)
        
    yield _db

async def ensure_db():
    async with _connect() as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()

async def store_experience(task_description: str, action_taken: str, outcome: str, success: bool) -> HindsightExperience:
    await ensure_db()
    exp = HindsightExperience(
        id=str(uuid.uuid4()),
        task_description=task_description,
        action_taken=action_taken,
        outcome=outcome,
        success=success
    )
    async with _connect() as db:
        await db.execute(
            """INSERT INTO hindsight_experiences (id, task_description, action_taken, outcome, success, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (exp.id, exp.task_description, exp.action_taken, exp.outcome, 1 if exp.success else 0, exp.created_at.isoformat())
        )
        await db.commit()
    return exp

async def get_experience(exp_id: str) -> HindsightExperience | None:
    await ensure_db()
    async with _connect() as db:
        cur = await db.execute("SELECT * FROM hindsight_experiences WHERE id = ?", (exp_id,))
        row = await cur.fetchone()
        if row:
            return HindsightExperience(
                id=row["id"],
                task_description=row["task_description"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
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
    
    async with _connect() as db:
        await db.execute(
            """INSERT INTO hindsight_learnings (id, experience_id, lesson, advice_for_future, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (learning.id, learning.experience_id, learning.lesson, learning.advice_for_future, learning.created_at.isoformat())
        )
        if embedding:
            emb_blob = sqlite_vec.serialize_float32(embedding)
            await db.execute(
                "INSERT INTO hindsight_vec (learning_id, embedding) VALUES (?, ?)",
                (learning.id, emb_blob)
            )
        await db.commit()
    return learning

async def search_advice(current_task: str, limit: int = 3) -> list[HindsightLearning]:
    await ensure_db()
    
    # fallback jika tak pake model embedding / get_embedding failed, we skip vector search
    try:
        query_emb = await get_embedding(current_task)
    except Exception as e:
        logger.warning(f"Embedding failed. Cannot perform hindsight search: {e}")
        return []
        
    emb_blob = sqlite_vec.serialize_float32(query_emb)
    
    async with _connect() as db:
        sql = """
        SELECT l.id, l.experience_id, l.lesson, l.advice_for_future, l.created_at,
               vec_distance_L2(v.embedding, ?) AS distance
        FROM hindsight_vec v
        JOIN hindsight_learnings l ON v.learning_id = l.id
        ORDER BY distance ASC
        LIMIT ?
        """
        cur = await db.execute(sql, (emb_blob, limit))
        results = []
        for row in await cur.fetchall():
            results.append(HindsightLearning(
                id=row["id"],
                experience_id=row["experience_id"],
                lesson=row["lesson"],
                advice_for_future=row["advice_for_future"]
            ))
        return results
