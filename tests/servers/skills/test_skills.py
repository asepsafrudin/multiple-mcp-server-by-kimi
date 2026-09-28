"""Tests for the skills engine and on-disk loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from servers.skills import engine, loader
from shared.models import Skill

# Queries that used to crash the raw FTS5 MATCH leg (TASK-140).
FTS_TRIGGER_QUERIES = ["C++", "(test", "search OR", 'unbalanced "quote']


def _skill(name: str, **kwargs) -> Skill:
    defaults = {
        "description": f"Description for {name}",
        "prompt_template": f"You are expert at {name}.",
        "triggers": [name],
    }
    defaults.update(kwargs)
    return Skill(name=name, **defaults)


async def test_register_and_load() -> None:
    sid = await engine.register(_skill("python-refactor"))
    assert sid
    loaded = await engine.load_skill("python-refactor", "global")
    assert loaded is not None
    assert loaded.name == "python-refactor"


async def test_register_upsert_same_name() -> None:
    await engine.register(_skill("mytest", namespace="coding"))
    await engine.register(_skill("mytest", namespace="coding", category="devops"))
    skills = await engine.list_skills(namespace="coding", category="devops")
    assert len(skills) == 1


async def test_recall() -> None:
    await engine.register(_skill("docker-deploy", triggers=["docker", "deploy"]))
    results = await engine.recall(query="docker deployment", limit=5)
    assert any(r["name"] == "docker-deploy" for r in results)


@pytest.mark.parametrize("query", FTS_TRIGGER_QUERIES)
async def test_recall_survives_fts5_operator_queries(query: str) -> None:
    """Regression TASK-140: operator queries must not raise a search error."""
    await engine.register(
        _skill("cpp-ops", description="C++ operator overload (test) search OR quote")
    )
    results = await engine.recall(query=query, limit=5)
    assert isinstance(results, list)


async def test_recall_falls_back_to_like_when_match_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second safety net: an FTS5 rejection must degrade to LIKE, not raise."""
    await engine.register(_skill("fb-skill", description="fallback marker xyzzy"))

    fallback_calls: list[str] = []
    original = engine._like_fallback

    async def _spy(db, *, query, namespace, limit):
        fallback_calls.append(query)
        return await original(db, query=query, namespace=namespace, limit=limit)

    monkeypatch.setattr(engine, "sanitize_fts_match", lambda _query: "(((")
    monkeypatch.setattr(engine, "_like_fallback", _spy)

    results = await engine.recall(query="fallback marker", limit=5)
    assert fallback_calls, "LIKE fallback was not triggered"
    assert any(item.get("name") == "fb-skill" for item in results)


async def test_list_skills() -> None:
    await engine.register(_skill("skill-a", namespace="ns1"))
    await engine.register(_skill("skill-b", namespace="ns2"))
    results = await engine.list_skills(namespace="ns1")
    assert [r.name for r in results] == ["skill-a"]


async def test_update_skill() -> None:
    await engine.register(_skill("upd", namespace="ns"))
    ok = await engine.update("upd", "ns", {"description": "updated desc"})
    assert ok is True
    loaded = await engine.load_skill("upd", "ns")
    assert loaded is not None
    assert loaded.description == "updated desc"


async def test_delete_skill() -> None:
    await engine.register(_skill("delme"))
    assert await engine.delete_skill("delme", "global") is True
    assert await engine.load_skill("delme", "global") is None
    assert await engine.delete_skill("delme", "global") is False


def test_loader_loads_json(tmp_path: Path) -> None:
    data = [
        {
            "name": "jsonSkill",
            "namespace": "global",
            "description": "desc",
            "prompt_template": "template",
            "triggers": ["json"],
        }
    ]
    (tmp_path / "s1.json").write_text(json.dumps(data), encoding="utf-8")
    skills = loader.load_skills_from_disk(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "jsonSkill"


def test_loader_skips_invalid(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text('{"name": 123}', encoding="utf-8")
    skills = loader.load_skills_from_disk(tmp_path)
    assert skills == []


def test_loader_empty_dir(tmp_path: Path) -> None:
    assert loader.load_skills_from_disk(tmp_path) == []
