"""Standard CLI runner for FastMCP servers."""

from __future__ import annotations

import argparse
from typing import Any

from fastmcp import FastMCP


def run(mcp: FastMCP, *, default_transport: str = "stdio", default_port: int = 8000) -> None:
    """Parse CLI args and start the FastMCP server."""
    parser = argparse.ArgumentParser(description=f"Run {mcp.name} MCP server.")
    parser.add_argument(
        "--transport",
        default=default_transport,
        choices=["stdio", "sse", "ws"],
        help="Transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help=f"Port for SSE/WS transport (default: {default_port}).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE/WS transport (default: 127.0.0.1).",
    )
    args = parser.parse_args()

    kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in {"sse", "ws"}:
        kwargs["port"] = args.port
        kwargs["host"] = args.host
    mcp.run(**kwargs)
