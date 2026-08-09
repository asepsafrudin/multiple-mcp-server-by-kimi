#!/usr/bin/env python3
"""Perform a Model Context Protocol (MCP) handshake against a server in this suite.

This script is a minimal MCP *client*: it connects to one of the project's servers,
runs the protocol handshake (``initialize`` request then ``notifications/initialized``),
prints the negotiated handshake details, and lists the tools the server exposes.

Usage examples
--------------
SSE transport (server already running via ``make start``)::

    python scripts/handshake.py http://127.0.0.1:8000/sse

stdio transport (script spawns the server itself) — default core server::

    python scripts/handshake.py
    python scripts/handshake.py --module servers.memory.server
    python scripts/handshake.py --args "-m servers.knowledge.server --transport sse"

Exit codes
----------
0  handshake succeeded
1  handshake failed
2  usage / argument error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys
from pathlib import Path

# Make the project importable regardless of CWD (mirrors servers/*/server.py).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

PYTHON = ROOT / ".venv" / "bin" / "python"


async def handshake_stdio(module: str, args: str | None) -> None:
    """Handshake over stdio by spawning the server module as a subprocess."""
    cli_args = shlex.split(args) if args else []
    params = StdioServerParameters(
        command=str(PYTHON),
        args=["-m", module, *cli_args],
        env={"MCP_ROOT": str(ROOT)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        result = await session.initialize()
        await report(session, result)


async def handshake_sse(url: str) -> None:
    """Handshake over SSE against an already-running server endpoint."""
    async with sse_client(url) as (read, write), ClientSession(read, write) as session:
        result = await session.initialize()
        await report(session, result)


async def report(session: ClientSession, result) -> None:
    """Print the negotiated handshake details and the server's tool list."""
    try:
        info = json.dumps(result.serverInfo.model_dump())
        caps = json.dumps(result.capabilities.model_dump())
    except Exception:  # noqa: BLE001 - best-effort display
        info, caps = str(result.serverInfo), str(result.capabilities)

    print("=" * 62)
    print("MCP HANDSHAKE OK")
    print("=" * 62)
    print(f"protocolVersion : {result.protocolVersion}")
    print(f"serverInfo      : {info}")
    print(f"capabilities    : {caps}")

    tools = await session.list_tools()
    items = tools.tools if hasattr(tools, "tools") else tools
    print("-" * 62)
    print(f"Exposed tools ({len(items)}):")
    for tool in items:
        desc = (tool.description or "").splitlines()[0] if tool.description else ""
        print(f"  - {tool.name}: {desc}")
    print("=" * 62)


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="MCP handshake client for the mcp-aseps suite.")
    parser.add_argument(
        "sse_url",
        nargs="?",
        default=None,
        help="SSE endpoint (e.g. http://127.0.0.1:8000/sse). If omitted, uses stdio.",
    )
    parser.add_argument(
        "--module",
        default="servers.core.server",
        help="Python module to spawn for stdio transport (default: servers.core.server).",
    )
    parser.add_argument(
        "--args",
        default=None,
        help="Extra CLI args (shell-quoted) passed to the spawned server module.",
    )
    ns = parser.parse_args()

    try:
        if ns.sse_url:
            await handshake_sse(ns.sse_url)
        else:
            await handshake_stdio(ns.module, ns.args)
    except Exception as exc:  # noqa: BLE001 - surface a friendly failure
        print(f"HANDSHAKE FAILED: {exc!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
