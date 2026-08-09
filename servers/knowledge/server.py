"""MCP knowledge / workspace RAG server entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from servers.knowledge import engine, harvester
from shared.logging import configure_logging

configure_logging()

mcp = FastMCP(
    name="mcp-knowledge-server",
    instructions=(
        "Workspace RAG server. Index project files and retrieve relevant chunks "
        "using semantic + keyword hybrid search."
    ),
)


@mcp.tool()
async def knowledge_index(
    project: str, root: str | None = None, max_files: int | None = None
) -> dict:
    """Harvest and index a workspace project into searchable knowledge chunks.

    project: logical project name used for namespacing.
    root: optional absolute path to the project root (default: <workspace_root>/<project>).
    max_files: optional cap on files scanned this run.
    """
    root_path = Path(root) if root else None
    return await harvester.harvest_project(
        project=project,
        root=root_path,
        max_files=max_files,
    )


@mcp.tool()
async def knowledge_search(query: str, project: str | None = None, limit: int = 5) -> list[dict]:
    """Search knowledge chunks using hybrid semantic + keyword retrieval."""
    limit = min(limit, 20)
    return await engine.search(query=query, project=project, limit=limit)


@mcp.tool()
async def knowledge_stats(project: str | None = None) -> dict:
    """Return knowledge index statistics, optionally filtered by project."""
    return await engine.get_stats(project)


@mcp.tool()
async def knowledge_forget_project(project: str) -> dict:
    """Delete all knowledge chunks for a project."""
    return await engine.delete_project(project)


@mcp.tool()
async def knowledge_reindex(
    project: str, root: str | None = None, max_files: int | None = None
) -> dict:
    """Clear a project's knowledge index and re-harvest it."""
    await engine.delete_project(project)
    return await harvester.harvest_project(
        project=project,
        root=Path(root) if root else None,
        max_files=max_files,
    )


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp)
