#!/usr/bin/env python3
"""Sync PostgreSQL memories to local SQLite database, generating 768-dim embeddings.

Runs local Ollama server to backfill the embeddings for sqlite-vec compatibility.
"""

import asyncio
import os
import sys
import json
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg
from servers.memory import engine
from shared.config import get_settings
from shared.models import MemoryEntry
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.scripts.sync")

async def main():
    settings = get_settings()
    
    # We read PG connection from settings or direct environment variables
    pg_url = os.environ.get("DATABASE_URL") or settings.db_url
    if not pg_url:
        pg_url = "postgresql://mcp_user:e1856daa732e9e58ed4bae5b@localhost:5433/mcp_knowledge"
        
    print(f"Connecting to PostgreSQL: {pg_url}")
    print(f"SQLite target: {settings.memory_db_path}")
    
    try:
        conn = psycopg.connect(pg_url)
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return
        
    with conn.cursor() as cur:
        # Check if table exists
        cur.execute("SELECT to_regclass('memories');")
        res = cur.fetchone()
        if not res or not res[0]:
            print("PostgreSQL memories table not found. Nothing to sync.")
            conn.close()
            return
            
        cur.execute("""
            SELECT id::text, namespace, key, content, metadata
            FROM memories
        """)
        rows = cur.fetchall()
        
    print(f"Found {len(rows)} memories in PostgreSQL.")
    
    # Initialize SQLite table
    await engine.ensure_memories_table()
    
    success_count = 0
    for row in rows:
        pg_id, namespace, key, content, metadata_json = row
        
        # Parse metadata
        meta = {}
        if metadata_json:
            if isinstance(metadata_json, dict):
                meta = metadata_json
            else:
                try:
                    meta = json.loads(metadata_json)
                except Exception:
                    pass
                    
        # Map PG fields to MemoryEntry
        category = meta.get("category", "general")
        allowed_categories = {'pattern', 'error', 'learning', 'context', 'decision', 'general'}
        if category not in allowed_categories:
            category = "general"
        tags = meta.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []
            
        summary = meta.get("summary", key)
        project = meta.get("project", None)
        importance = int(meta.get("importance", 5))
        source = meta.get("source", None)
        
        entry = MemoryEntry(
            id=pg_id,
            namespace=namespace,
            content=content,
            summary=summary,
            category=category,
            tags=tags,
            importance=importance,
            quant_level="raw",
            memory_type="semantic",
            validation_status="verified",
            source=source,
            project=project,
        )
        
        try:
            # Check if already exists in SQLite
            existing = await engine.get_by_id(entry.id, entry.namespace)
            if existing:
                print(f"Skipping {entry.id} (already exists in SQLite)")
                continue
                
            print(f"Syncing and generating embedding for {entry.id}...")
            await engine.store(entry)
            success_count += 1
        except Exception as e:
            print(f"Failed to sync {entry.id}: {e}")
            
    print(f"Sync complete. Successful syncs: {success_count}/{len(rows)}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
