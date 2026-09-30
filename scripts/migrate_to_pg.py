#!/usr/bin/env python3
"""Migrasi data progresif dari SQLite (LTM & RAG) ke PostgreSQL."""

import asyncio
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aiosqlite
from shared.config import get_settings
from shared.pg_db import init_pg_db, close_pg_db, get_db_connection
from servers.memory.pg_engine import ensure_memories_table
from servers.knowledge.pg_engine import ensure_knowledge_tables

import sqlite_vec

def deserialize_vec(blob: bytes) -> list[float]:
    """Dekode struktur biner C dari sqlite-vec ke Python Array Float32"""
    if not blob:
        return []
    count = len(blob) // 4
    return list(struct.unpack(f'<{count}f', blob))

async def migrate_memory():
    settings = get_settings()
    db_path = settings.memory_db_path
    if not db_path.exists():
        print(f"[-] SQLite Memory DB tidak ditemukan di {db_path}, skip memori.")
        return

    print("[*] Memulai migrasi M E M O R Y ...")
    await ensure_memories_table()

    async with aiosqlite.connect(str(db_path), check_same_thread=False) as sqldb:
        await sqldb.execute("SELECT 1")
        sqldb._conn.enable_load_extension(True)
        sqlite_vec.load(sqldb._conn)
        sqldb._conn.enable_load_extension(False)
        sqldb.row_factory = aiosqlite.Row
        
        try:
            cur = await sqldb.execute("""
                SELECT m.*, v.embedding 
                FROM memories m 
                LEFT JOIN memory_vec v ON m.rowid = v.rowid
            """)
            rows = await cur.fetchall()
        except aiosqlite.OperationalError as e:
            if "no such table" in str(e).lower():
                print("    Tabel SQLite tidak eksis atau kosong. Skipping.")
                return
            raise e

    if not rows:
        print("    Data memory kosong.")
        return

    print(f"    Ditemukan {len(rows)} data memori di SQLite. Memindahkan ke PG...")
    inserted = 0
    async with get_db_connection() as conn:
        for row in rows:
            embedding = deserialize_vec(row["embedding"]) if row["embedding"] else None
            
            tags_raw = row["tags"]
            try:
                tags = json.dumps(json.loads(tags_raw)) if tags_raw else '[]'
            except:
                tags = '[]'

            try:
                await conn.execute(
                    """
                    INSERT INTO memories
                    (id, namespace, content, summary, category, tags, importance,
                     access_count, quant_level, memory_type, validation_status, source_task_id,
                     is_archived, source, project, embedding, created_at, updated_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        row["id"], row["namespace"], row["content"], row["summary"],
                        row["category"], tags, row["importance"], row["access_count"],
                        row["quant_level"], row["memory_type"], row["validation_status"],
                        row["source_task_id"], row["is_archived"], row["source"],
                        row["project"], embedding, row["created_at"], row["updated_at"],
                        row["expires_at"]
                    )
                )
                inserted += 1
            except Exception as e:
                print(f"    [!] Error insert memory ID {row['id']}: {e}")
        
        await conn.commit()

    print(f"    Berhasil memigrasikan {inserted} baris memori!\n")


async def migrate_knowledge():
    settings = get_settings()
    db_path = settings.knowledge_db_path
    if not db_path.exists():
        print(f"[-] SQLite Knowledge DB tidak ditemukan di {db_path}, skip knowledge.")
        return

    print("[*] Memulai migrasi K N O W L E D G E (RAG) ...")
    await ensure_knowledge_tables()

    async with aiosqlite.connect(str(db_path), check_same_thread=False) as sqldb:
        await sqldb.execute("SELECT 1")
        sqldb._conn.enable_load_extension(True)
        sqlite_vec.load(sqldb._conn)
        sqldb._conn.enable_load_extension(False)
        sqldb.row_factory = aiosqlite.Row
        try:
            cur = await sqldb.execute("""
                SELECT c.*, v.embedding 
                FROM knowledge_chunks c 
                LEFT JOIN knowledge_vec v ON c.rowid = v.rowid
            """)
            rows = await cur.fetchall()
        except aiosqlite.OperationalError as e:
            if "no such table" in str(e).lower():
                print("    Tabel SQLite tidak eksis atau kosong. Skipping.")
                return
            raise e

    if not rows:
        print("    Data knowledge kosong.")
        return

    print(f"    Ditemukan {len(rows)} chunks di SQLite. Memindahkan ke PG...")
    inserted = 0
    async with get_db_connection() as conn:
        for row in rows:
            embedding = deserialize_vec(row["embedding"]) if row["embedding"] else None
            
            meta_raw = row["metadata"]
            try:
                meta = json.dumps(json.loads(meta_raw)) if meta_raw else '{}'
            except:
                meta = '{}'

            try:
                await conn.execute(
                    """
                    INSERT INTO knowledge_chunks
                    (id, project, file_path, file_hash, file_type, chunk_index, total_chunks,
                     content, metadata, embedding, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        row["id"], row["project"], row["file_path"], row["file_hash"],
                        row["file_type"], row["chunk_index"], row["total_chunks"],
                        row["content"], meta, embedding, row["created_at"], row["updated_at"]
                    )
                )
                inserted += 1
            except Exception as e:
                print(f"    [!] Error insert chunk ID {row['id']}: {e}")
        
        await conn.commit()

    print(f"    Berhasil memigrasikan {inserted} chunk knowledge!\n")


from servers.memory.pg_hindsight_engine import ensure_db as ensure_hindsight_db
from servers.skills.pg_engine import ensure_skills_tables

async def migrate_hindsight():
    settings = get_settings()
    db_path = settings.hindsight_db_path
    if not db_path.exists():
        print(f"[-] SQLite Hindsight DB tidak ditemukan, skip hindsight.")
        return

    print("[*] Memulai migrasi H I N D S I G H T ...")
    await ensure_hindsight_db()

    async with aiosqlite.connect(str(db_path), check_same_thread=False) as sqldb:
        await sqldb.execute("SELECT 1")
        sqldb._conn.enable_load_extension(True)
        sqlite_vec.load(sqldb._conn)
        sqldb._conn.enable_load_extension(False)
        sqldb.row_factory = aiosqlite.Row
        
        try:
            cur = await sqldb.execute("SELECT * FROM hindsight_experiences")
            exps = await cur.fetchall()
            
            cur2 = await sqldb.execute("""
                SELECT l.*, v.embedding 
                FROM hindsight_learnings l
                LEFT JOIN hindsight_vec v ON l.id = v.learning_id
            """)
            learnings = await cur2.fetchall()
        except Exception as e:
            print("    Tabel SQLite hindsight error. Skipping.", str(e))
            return

    async with get_db_connection() as conn:
        for exp in exps:
            await conn.execute(
                """INSERT INTO hindsight_experiences (id, task_description, action_taken, outcome, success, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (exp["id"], exp["task_description"], exp["action_taken"], exp["outcome"], exp["success"], exp["created_at"])
            )
        
        for l in learnings:
            embedding = deserialize_vec(l["embedding"]) if l["embedding"] else None
            await conn.execute(
                """INSERT INTO hindsight_learnings (id, experience_id, lesson, advice_for_future, created_at, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (l["id"], l["experience_id"], l["lesson"], l["advice_for_future"], l["created_at"], embedding)
            )
        await conn.commit()

    print(f"    Berhasil memigrasikan {len(exps)} Experiences dan {len(learnings)} Learnings!\n")


async def migrate_skills():
    settings = get_settings()
    db_path = Path("/home/aseps/MCP/data/skills_v2.db")
    if getattr(settings, 'skills_db_path', None):
        db_path = settings.skills_db_path

    if not db_path.exists():
        print(f"[-] SQLite Skills DB tidak ditemukan, skip skills.")
        return

    print("[*] Memulai migrasi S K I L L S ...")
    await ensure_skills_tables()

    async with aiosqlite.connect(str(db_path), check_same_thread=False) as sqldb:
        await sqldb.execute("SELECT 1")
        sqldb._conn.enable_load_extension(True)
        sqlite_vec.load(sqldb._conn)
        sqldb._conn.enable_load_extension(False)
        sqldb.row_factory = aiosqlite.Row
        
        try:
            cur = await sqldb.execute("""
                SELECT s.*, v.embedding 
                FROM skills s
                LEFT JOIN skill_vec v ON s.rowid = v.rowid
            """)
            rows = await cur.fetchall()
        except Exception as e:
            print("    Tabel SQLite skills error. Skipping.", str(e))
            return

    inserted = 0
    async with get_db_connection() as conn:
        for row in rows:
            embedding = deserialize_vec(row["embedding"]) if row["embedding"] else None
            
            def safe_json(val):
                try:
                    return json.dumps(json.loads(val)) if val else None
                except:
                    return val if val else None
            
            await conn.execute(
                """
                INSERT INTO skills
                (id, name, namespace, description, category, script_path,
                 metadata, schema, prompt_template, triggers, embedding, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    row["id"], row["name"], row["namespace"], row["description"],
                    row["category"], row["script_path"], safe_json(row["metadata"]) or '{}',
                    safe_json(row["schema"]) or '{}', row["prompt_template"],
                    safe_json(row["triggers"]) or '[]', embedding, row["created_at"], row["updated_at"]
                )
            )
            inserted += 1
        await conn.commit()

    print(f"    Berhasil memigrasikan {inserted} Skills!\n")



async def main():
    print("====================================")
    print(" UTILIAS MIGRASI DATABASE MCP (v4.0)")
    print("====================================\n")
    
    await init_pg_db()
    
    await migrate_memory()
    await migrate_knowledge()
    await migrate_hindsight()
    await migrate_skills()
    
    await close_pg_db()
    print("Proses Migrasi Selesai! Data lama SQLite Anda siap beroperasi di Postgres.")




if __name__ == "__main__":
    asyncio.run(main())
