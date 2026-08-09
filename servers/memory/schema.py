"""SQL schema for the LTM memory table."""

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    is_archived       BOOLEAN NOT NULL DEFAULT FALSE,
    source            TEXT,
    project           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ,
    embedding         vector(768)
);

CREATE INDEX IF NOT EXISTS idx_memories_namespace  ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_category   ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_project    ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created    ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_expires    ON memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_memories_archived   ON memories(is_archived);
CREATE INDEX IF NOT EXISTS idx_memories_fts        ON memories USING GIN (to_tsvector('indonesian', content));
CREATE INDEX IF NOT EXISTS idx_memories_embedding  ON memories USING hnsw (embedding vector_cosine_ops);
"""
