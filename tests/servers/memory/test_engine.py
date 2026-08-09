"""Tests for the memory engine (SQLite + sqlite-vec + FTS5)."""

from __future__ import annotations

from datetime import UTC

from servers.memory import engine
from shared.models import MemoryEntry


async def _store(namespace: str, content: str, **kwargs) -> str:
    entry = MemoryEntry(namespace=namespace, content=content, **kwargs)
    return await engine.store(entry)


async def test_store_and_recall() -> None:
    mid = await _store("agent-a", "User prefers Indonesian responses.", importance=9)
    assert mid
    results = await engine.recall(query="preferred language", namespace="agent-a")
    assert len(results) >= 1
    assert results[0].content == "User prefers Indonesian responses."


async def test_recall_respects_namespace() -> None:
    await _store("ns1", "Alpha memory content")
    await _store("ns2", "Entirely different beta content here")
    results = await engine.recall(query="Alpha memory", namespace="ns1")
    assert any("Alpha" in r.content for r in results)
    assert not any("beta" in r.content for r in results)


async def test_search_by_filters() -> None:
    await _store("ns", "Decision to use SQLite", category="decision", project="mcp", tags=["db"])
    await _store("ns", "A learning note", category="learning", project="other")
    results = await engine.search_by_filters(namespace="ns", category="decision", project="mcp")
    assert len(results) == 1
    assert results[0].category == "decision"


async def test_update_memory() -> None:
    mid = await _store("ns", "original content", importance=3)
    ok = await engine.update(mid, "ns", {"content": "updated content", "importance": 8})
    assert ok is True
    entry = await engine.get_by_id(mid, "ns")
    assert entry is not None
    assert entry.content == "updated content"
    assert entry.importance == 8


async def test_quantize_summary() -> None:
    mid = await _store("ns", "long content " * 50)
    ok = await engine.quantize(mid, "ns", "summary")
    assert ok is True
    entry = await engine.get_by_id(mid, "ns")
    assert entry is not None
    assert entry.quant_level == "summary"
    assert entry.summary is not None
    assert len(entry.summary) <= 303


async def test_delete_memory() -> None:
    mid = await _store("ns", "to be deleted")
    assert await engine.delete(mid, "ns") is True
    assert await engine.get_by_id(mid, "ns") is None
    assert await engine.delete(mid, "ns") is False


async def test_cleanup_expired() -> None:
    from datetime import datetime, timedelta

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    mid = await _store("ns", "expired memory", expires_at=past)
    cleaned = await engine.cleanup_expired()
    assert cleaned >= 1
    assert await engine.get_by_id(mid, "ns") is None


async def test_get_stats() -> None:
    await _store("ns", "stat-one", category="general")
    await _store("ns", "stat-two", category="learning")
    stats = await engine.get_stats("ns")
    assert stats["total_memories"] >= 2
    assert "general" in stats["categories"]
