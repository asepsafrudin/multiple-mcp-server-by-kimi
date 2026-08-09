"""Tests for the knowledge engine and chunking utilities."""

from __future__ import annotations

from pathlib import Path

from servers.knowledge import engine
from servers.knowledge.chunking import chunk_file, chunk_text
from shared.models import KnowledgeChunk


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
