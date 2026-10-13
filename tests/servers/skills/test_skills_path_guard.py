"""TASK-139 regression: skill_load_registry menolak registry_dir di luar allowed."""

from __future__ import annotations

import asyncio

from servers.skills.server import skill_load_registry


def test_skill_load_registry_rejects_outside_allowed():
    res = asyncio.run(skill_load_registry(registry_dir="/etc"))
    assert res.get("status") == "error"
    assert "not allowed" in res.get("error", "").lower()
