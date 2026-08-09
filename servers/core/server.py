"""MCP core tools server entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a module.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from shared.logging import configure_logging
from servers.core import filesystem, shell, system, web, security

configure_logging()

mcp = FastMCP(
    name="mcp-core-tools",
    instructions=(
        "Core system tools: filesystem, shell, system info, web, and security. "
        "All filesystem operations are sandboxed to allowed directories."
    ),
)


# Filesystem tools
@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a text file from an allowed directory."""
    return await filesystem.read_file(path, encoding)


@mcp.tool()
async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write text content to a file inside an allowed directory."""
    return await filesystem.write_file(path, content, encoding)


@mcp.tool()
async def list_directory(path: str = ".", show_hidden: bool = False) -> list[dict]:
    """List directory contents with basic metadata."""
    return await filesystem.list_directory(path, show_hidden)


@mcp.tool()
async def search_files(
    directory: str, pattern: str, recursive: bool = True, max_results: int = 50
) -> list[str]:
    """Search files by glob pattern inside an allowed directory."""
    return await filesystem.search_files(directory, pattern, recursive, max_results)


@mcp.tool()
async def delete_file(path: str) -> str:
    """Delete a file. This operation cannot be undone."""
    return await filesystem.delete_file(path)


@mcp.tool()
async def move_file(source: str, destination: str) -> str:
    """Move or rename a file within allowed directories."""
    return await filesystem.move_file(source, destination)


# Shell tools
@mcp.tool()
async def run_shell(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    env_extras: dict | None = None,
) -> dict:
    """Run a single whitelisted shell command inside an allowed working directory."""
    return await shell.run_shell(command, cwd, timeout, env_extras)


# System tools
@mcp.tool()
async def get_system_info() -> dict:
    """Return host system statistics (CPU, memory, OS, Python version)."""
    return await system.get_system_info()


@mcp.tool()
async def get_env_variable(name: str) -> dict:
    """Read a non-sensitive environment variable."""
    return await system.get_env_variable(name)


# Web tools
@mcp.tool()
async def fetch_url(
    url: str, extract_text: bool = True, timeout: int = 30, max_chars: int = 10000
) -> dict:
    """Fetch content from a URL; optionally strip HTML tags."""
    return await web.fetch_url(url, extract_text, timeout, max_chars)


@mcp.tool()
async def check_url_status(url: str, timeout: int = 10) -> dict:
    """Check whether a URL is reachable via HEAD request."""
    return await web.check_url_status(url, timeout)


# Security tools
@mcp.tool()
async def validate_input(value: str, schema_type: str, max_length: int = 1000) -> dict:
    """Validate an input string against a schema (email, url, uuid, alphanumeric, safe_string)."""
    return await security.validate_input(value, schema_type, max_length)


@mcp.tool()
async def sanitize_string(text: str, max_length: int = 10000) -> str:
    """Sanitize a string by removing dangerous characters."""
    return await security.sanitize_string(text, max_length)


@mcp.tool()
async def audit_log(
    action: str, resource: str, result: str, metadata: dict | None = None
) -> str:
    """Append a structured audit log entry."""
    return await security.audit_log(action, resource, result, metadata)


@mcp.tool()
async def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Hash a string using sha256, sha512, or md5 (md5 for checksums only)."""
    return await security.hash_string(text, algorithm)


if __name__ == "__main__":
    from shared.server_runner import run
    run(mcp)
