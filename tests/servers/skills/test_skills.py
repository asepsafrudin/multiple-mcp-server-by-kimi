"""Tests for the skills engine and on-disk loader."""

from __future__ import annotations

import json
from pathlib import Path

from servers.skills import engine, loader
from shared.models import Skill


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
