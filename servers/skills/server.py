"""MCP skill registry / procedural memory server entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from servers.skills import engine, loader
from shared.config import get_settings
from shared.logging import configure_logging
from shared.models import Skill

configure_logging()

mcp = FastMCP(
    name="mcp-skills-server",
    instructions=(
        "Procedural memory / skill registry. Register, recall, and load reusable "
        "prompt patterns and tool workflows for agentic tasks."
    ),
)


@mcp.tool()
async def skill_register(
    name: str,
    description: str,
    prompt_template: str,
    namespace: str = "global",
    category: str = "general",
    triggers: list[str] | None = None,
    tools_required: list[str] | None = None,
    examples: list[str] | None = None,
    version: int = 1,
) -> dict:
    """Register a reusable skill / procedural memory pattern."""
    skill = Skill(
        name=name,
        namespace=namespace,
        category=category,
        description=description,
        triggers=triggers or [],
        prompt_template=prompt_template,
        tools_required=tools_required or [],
        examples=examples or [],
        version=version,
    )
    skill_id = await engine.register(skill)
    return {"status": "registered", "id": skill_id, "name": name, "namespace": namespace}


@mcp.tool()
async def skill_recall(query: str, namespace: str | None = None, limit: int = 5) -> list[dict]:
    """Recall skills matching the query using semantic + keyword search."""
    limit = min(limit, 20)
    return await engine.recall(query=query, namespace=namespace, limit=limit)


@mcp.tool()
async def skill_list(
    namespace: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List registered skills."""
    limit = min(limit, 200)
    skills = await engine.list_skills(namespace=namespace, category=category, limit=limit)
    return [
        {
            "id": s.id,
            "name": s.name,
            "namespace": s.namespace,
            "category": s.category,
            "description": s.description,
            "triggers": s.triggers,
            "tools_required": s.tools_required,
            "version": s.version,
        }
        for s in skills
    ]


@mcp.tool()
async def skill_load(name: str, namespace: str = "global") -> dict:
    """Load a single skill's full prompt template."""
    skill = await engine.load_skill(name=name, namespace=namespace)
    if not skill:
        return {"status": "not_found", "name": name, "namespace": namespace}
    return {
        "status": "loaded",
        "skill": {
            "id": skill.id,
            "name": skill.name,
            "namespace": skill.namespace,
            "category": skill.category,
            "description": skill.description,
            "triggers": skill.triggers,
            "prompt_template": skill.prompt_template,
            "tools_required": skill.tools_required,
            "examples": skill.examples,
            "version": skill.version,
        },
    }


@mcp.tool()
async def skill_update(
    name: str,
    namespace: str,
    updates: dict,
) -> dict:
    """Update specific fields of an existing skill."""
    success = await engine.update(name=name, namespace=namespace, updates=updates)
    return {"status": "updated" if success else "not_found", "name": name, "namespace": namespace}


@mcp.tool()
async def skill_delete(name: str, namespace: str = "global") -> dict:
    """Delete a skill by name and namespace."""
    deleted = await engine.delete_skill(name=name, namespace=namespace)
    return {"status": "deleted" if deleted else "not_found", "name": name, "namespace": namespace}


@mcp.tool()
async def skill_load_registry(registry_dir: str | None = None) -> dict:
    """Bulk-load skill definitions from a directory of YAML/JSON files."""
    settings = get_settings()
    path = Path(registry_dir) if registry_dir else settings.mcp_root / "skills" / "registry"
    skills = loader.load_skills_from_disk(path)
    registered = 0
    for skill in skills:
        await engine.register(skill)
        registered += 1
    return {"status": "loaded", "registry": str(path), "registered": registered}


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp)
