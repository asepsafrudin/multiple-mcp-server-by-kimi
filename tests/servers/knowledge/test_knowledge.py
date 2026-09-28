"""Tests for the knowledge engine and chunking utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from servers.knowledge import engine
from servers.knowledge.chunking import chunk_file, chunk_text
from shared.models import KnowledgeChunk

# Queries that used to crash the raw FTS5 MATCH leg (TASK-140).
FTS_TRIGGER_QUERIES = ["C++", "(test", "search OR", 'unbalanced "quote']


def test_chunk_text_splits_long_text() -> None:
    text = "\n\n".join(f"Paragraph {i} " + "word " * 200 for i in range(10))
    chunks = chunk_text(text, max_tokens=100, overlap_tokens=10)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_chunk_text_single_small_text() -> None:
    chunks = chunk_text("Hello world", max_tokens=500)
    assert chunks == ["Hello world"]


def test_chunk_file_markdown_uses_lower_token_budget(tmp_path: Path) -> None:
    f = tmp_path / "doc.md"
    text = "word " * 1000
    chunks = chunk_file(f, text)
    assert len(chunks) >= 1


async def _make_chunk(project: str, file_path: str, content: str, idx: int = 0) -> KnowledgeChunk:
    return KnowledgeChunk(
        project=project,
        file_path=file_path,
        file_hash="abc123",
        file_type=file_path.rsplit(".", 1)[-1],
        chunk_index=idx,
        total_chunks=1,
        content=content,
    )


async def test_index_and_search() -> None:
    chunk = await _make_chunk("proj", "main.py", "def fastmcp_route(): pass")
    res = await engine.index_chunks([chunk])
    assert res["indexed"] == 1

    results = await engine.search("fastmcp route", project="proj")
    assert len(results) >= 1
    assert results[0]["file_path"] == "main.py"


async def test_index_is_idempotent() -> None:
    chunk = await _make_chunk("proj", "a.py", "content v1")
    await engine.index_chunks([chunk])
    chunk2 = await _make_chunk("proj", "a.py", "content v2")
    res = await engine.index_chunks([chunk2])
    assert res["indexed"] == 1
    stats = await engine.get_stats("proj")
    assert stats["total_chunks"] == 1
    assert stats["unique_files"] == 1


async def test_delete_project() -> None:
    chunk = await _make_chunk("proj", "x.py", "some content")
    await engine.index_chunks([chunk])
    res = await engine.delete_project("proj")
    assert res["chunks_removed"] == 1
    stats = await engine.get_stats("proj")
    assert stats["total_chunks"] == 0


async def test_get_stats() -> None:
    chunk = await _make_chunk("proj", "app.py", "def main(): pass")
    await engine.index_chunks([chunk])
    stats = await engine.get_stats("proj")
    assert stats["total_chunks"] == 1
    assert "py" in stats["file_types"]


@pytest.mark.parametrize("query", FTS_TRIGGER_QUERIES)
async def test_search_survives_fts5_operator_queries(query: str) -> None:
    """Regression TASK-140: operator queries must not raise a search error."""
    chunk = await _make_chunk("proj", "ops.cpp", "C++ operator overload (test) search OR quote")
    await engine.index_chunks([chunk])
    results = await engine.search(query, project="proj")
    assert isinstance(results, list)


async def test_search_falls_back_to_like_when_match_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second safety net: an FTS5 rejection must degrade to LIKE, not raise."""
    chunk = await _make_chunk("proj", "fb.py", "fallback marker xyzzy")
    await engine.index_chunks([chunk])

    fallback_calls: list[str] = []
    original = engine._like_fallback

    async def _spy(db, *, query, project, limit):
        fallback_calls.append(query)
        return await original(db, query=query, project=project, limit=limit)

    monkeypatch.setattr(engine, "sanitize_fts_match", lambda _query: "(((")
    monkeypatch.setattr(engine, "_like_fallback", _spy)

    results = await engine.search("fallback marker", project="proj")
    assert fallback_calls, "LIKE fallback was not triggered"
    assert any(isinstance(item, dict) and item.get("file_path") == "fb.py" for item in results)
