import asyncio
import pytest
from shared.models import MemoryEntry
from servers.memory import pg_engine as engine
from shared.pg_db import init_pg_db, close_pg_db

async def _store(namespace: str, content: str, **kwargs) -> str:
    entry = MemoryEntry(namespace=namespace, content=content, **kwargs)
    return await engine.store(entry)

async def run_tests():
    await init_pg_db()
    
    # test_store_and_get
    mid = await _store("test_ns", "Some pg memory", category="general", tags=["pg"])
    entry = await engine.get_by_id(mid, "test_ns")
    assert entry.content == "Some pg memory"
    assert entry.category == "test"
    assert "pg" in entry.tags
    print("test_store_and_get: PASSED")

    # test_recall_semantic
    await _store("test_ns", "Pineapple goes on pizza", category="fact")
    res = await engine.recall("Pineapple pizza", "test_ns", limit=1)
    assert len(res) >= 1
    assert "Pineapple" in res[0].content
    print("test_recall_semantic: PASSED")
    
    # test_search_by_filters
    await _store("test_ns", "Decision to use Postgres", category="decision", project="mcp", tags=["db"])
    res = await engine.search_by_filters(namespace="test_ns", category="decision", project="mcp")
    assert any(r.category == "decision" for r in res)
    print("test_search_by_filters: PASSED")
    
    # test_update_memory
    update_mid = await _store("test_ns", "original content", importance=3)
    ok = await engine.update(update_mid, "test_ns", {"content": "updated content", "importance": 8})
    assert ok is True
    updated = await engine.get_by_id(update_mid, "test_ns")
    assert updated.content == "updated content"
    assert updated.importance == 8
    print("test_update_memory: PASSED")
    
    # test_delete_memory
    del_mid = await _store("test_ns", "to be deleted")
    assert await engine.delete(del_mid, "test_ns") is True
    assert await engine.get_by_id(del_mid, "test_ns") is None
    print("test_delete_memory: PASSED")
    
    await close_pg_db()

asyncio.run(run_tests())
