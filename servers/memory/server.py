"""MCP long-term memory server entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import UTC

from fastmcp import FastMCP

from servers.memory import engine
from servers.memory import hindsight_engine
from shared.logging import configure_logging
from shared.models import MemoryEntry

configure_logging()

mcp = FastMCP(
    name="mcp-memory-server",
    instructions=(
        "Persistent long-term memory server. Store facts, decisions, errors, "
        "context, and patterns. Use memory_recall for semantic retrieval."
    ),
)


@mcp.tool()
async def memory_store(
    namespace: str,
    content: str,
    category: str = "general",
    memory_type: str = "semantic",
    validation_status: str = "pending",
    source_task_id: str | None = None,
    tags: list[str] | None = None,
    importance: int = 5,
    summary: str | None = None,
    project: str | None = None,
    source: str | None = None,
    expires_in_days: int | None = None,
) -> dict:
    """Save a memory to long-term storage.

    category: general | decision | learning | context | error | pattern
    importance: 1-10
    expires_in_days: optional TTL after which the memory is auto-deleted.
    """
    from datetime import datetime, timedelta

    expires_at = None
    if expires_in_days is not None:
        expires_at = (datetime.now(UTC) + timedelta(days=expires_in_days)).isoformat()

    entry = MemoryEntry(
        namespace=namespace,
        content=content,
        summary=summary,
        category=category,
        memory_type=memory_type,
        validation_status=validation_status,
        source_task_id=source_task_id,
        tags=tags or [],
        importance=importance,
        source=source,
        project=project,
        expires_at=expires_at,
    )
    memory_id = await engine.store(entry)
    return {"status": "stored", "id": memory_id, "category": category, "importance": importance}


@mcp.tool()
async def memory_recall(
    namespace: str,
    query: str,
    limit: int = 5,
    category: str | None = None,
    project: str | None = None,
    min_importance: int = 1,
) -> list[dict]:
    """Recall relevant memories using hybrid semantic + keyword search."""
    limit = min(limit, 20)
    results = await engine.recall(
        query=query,
        namespace=namespace,
        limit=limit,
        category=category,
        project=project,
        min_importance=min_importance,
    )
    if not results:
        return [{"status": "no_results", "message": f"No memories match: '{query}'"}]
    return [r.to_compact() for r in results]


@mcp.tool()
async def memory_search(
    namespace: str,
    tags: list[str] | None = None,
    category: str | None = None,
    project: str | None = None,
    since_days: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search memories using structured filters (tags, category, project, recency)."""
    limit = min(limit, 50)
    results = await engine.search_by_filters(
        namespace=namespace,
        tags=tags,
        category=category,
        project=project,
        since_days=since_days,
        limit=limit,
    )
    if not results:
        return [{"status": "no_results", "message": "No memories match the filters."}]
    return [r.to_compact() for r in results]


@mcp.tool()
async def memory_forget(namespace: str, id: str) -> dict:
    """Delete a memory by ID."""
    deleted = await engine.delete(id, namespace)
    if deleted:
        return {"status": "deleted", "id": id}
    return {"status": "not_found", "id": id}


@mcp.tool()
async def memory_update(
    namespace: str,
    id: str,
    updates: dict,
) -> dict:
    """Update specific fields of an existing memory."""
    success = await engine.update(id, namespace, updates)
    return {"status": "updated" if success else "not_found", "id": id}


@mcp.tool()
async def memory_quantize(namespace: str, id: str, level: str = "summary") -> dict:
    """Compress a memory to 'summary' or 'compressed' level."""
    if level not in {"summary", "compressed"}:
        raise ValueError("level must be 'summary' or 'compressed'")
    success = await engine.quantize(id, namespace, level)
    return {"status": "quantized" if success else "not_found", "id": id, "level": level}


@mcp.tool()
async def memory_evaluate(namespace: str, id: str, new_status: str) -> dict:
    """Change validation status: pending | verified | rejected."""
    success = await engine.update(id, namespace, {"validation_status": new_status})
    return {"status": "evaluated" if success else "not_found", "id": id, "new_status": new_status}


@mcp.tool()
async def memory_stats(namespace: str | None = None) -> dict:
    """Return memory statistics, optionally filtered by namespace."""
    cleaned = await engine.cleanup_expired()
    stats = await engine.get_stats(namespace)
    stats["cleaned_expired"] = cleaned
    return stats


@mcp.tool()
async def hindsight_store_experience(task_description: str, action_taken: str, outcome: str, success: bool) -> dict:
    """Store an agent's experience after attempting a task. Useful for learning what works and what doesn't."""
    exp = await hindsight_engine.store_experience(task_description, action_taken, outcome, success)
    return {"status": "stored", "experience_id": exp.id}


@mcp.tool()
async def hindsight_reflect_and_learn(experience_id: str, lesson: str, advice_for_future: str) -> dict:
    """Derive learning from a past experience and save it as advice for similar future tasks."""
    try:
        learning = await hindsight_engine.reflect_and_learn(experience_id, lesson, advice_for_future)
        return {"status": "learned", "learning_id": learning.id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def hindsight_search_advice(current_task: str, limit: int = 3) -> list[dict]:
    """Retrieve relevant past advice and learnings when facing a new task."""
    learnings = await hindsight_engine.search_advice(current_task, limit)
    return [
        {
            "id": l.id,
            "lesson": l.lesson,
            "advice": l.advice_for_future,
            "experience_id": l.experience_id
        }
        for l in learnings
    ]


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp)
