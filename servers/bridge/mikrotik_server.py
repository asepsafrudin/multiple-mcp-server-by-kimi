"""MCP bridge server for MikroTik RouterOS management.

Connects to a MikroTik RouterBoard over two transports:

* **RouterOS REST API** (RouterOS v7 / v6.48.2+, enabled via the ``www-ssl``
  service on port 443 by default) — structured read/write against resources
  such as ``/interface``, ``/system/resource``, ``/ip/address``.
* **SSH** (RouterOS SSH service) — free-form CLI commands, e.g. ``/export``
  or ``/tool/ping``.

Credentials come from environment variables / `.env`:

  MIKROTIK_HOST       - IP or hostname of the router
  MIKROTIK_PORT       - REST API port (default 443)
  MIKROTIK_USER       - RouterOS user (group with full/read permissions)
  MIKROTIK_PASSWORD   - Password for that user
  MIKROTIK_SCHEME     - http or https (default https)
  MIKROTIK_TLS_VERIFY - validate TLS cert (default false, self-signed allowed)
  MIKROTIK_SSH_PORT   - SSH port (default 22)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from fastmcp import FastMCP

from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.bridge.mikrotik")

mcp = FastMCP(
    name="mcp-mikrotik-bridge",
    instructions=(
        "MikroTik RouterOS bridge. Configure MIKROTIK_HOST, MIKROTIK_USER and "
        "MIKROTIK_PASSWORD. REST API (RouterOS v7, www-ssl enabled) plus SSH."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_host() -> str:
    settings = get_settings()
    if not settings.mikrotik_host:
        raise RuntimeError(
            "MIKROTIK_HOST not configured. Set MIKROTIK_HOST, MIKROTIK_USER and "
            "MIKROTIK_PASSWORD in .env."
        )
    return settings.mikrotik_host


def _client() -> httpx.AsyncClient:
    """Build an AsyncClient with Basic auth and (optionally) relaxed TLS."""
    settings = get_settings()
    return httpx.AsyncClient(
        auth=httpx.BasicAuth(settings.mikrotik_user or "", settings.mikrotik_password or ""),
        timeout=30.0,
        verify=settings.mikrotik_tls_verify,
    )


def _rest_url(path: str) -> str:
    settings = get_settings()
    base = f"{settings.mikrotik_scheme}://{_require_host()}:{settings.mikrotik_port}"
    clean = path.lstrip("/")
    return f"{base}/rest/{clean}"


async def _rest_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _rest_url(path)
    async with _client() as client:
        response = await client.request(
            method.upper(), url, params=params, json=json_body
        )
        response.raise_for_status()
        data = None
        if response.content:
            data = response.json()
        return {"status": "ok", "method": method.upper(), "path": path, "data": data}

# ---------------------------------------------------------------------------
# RouterOS REST API tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def mikrotik_run_rest(
    path: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict:
    """Call an arbitrary RouterOS REST endpoint.

    Args:
        path: resource path without a leading slash, e.g. "interface",
            "ip/address", "system/identity" or "tool/ping".
        method: HTTP method (GET, PUT, POST, PATCH, DELETE). Default "GET".
        params: optional query-string parameters.
        json_body: optional JSON payload (used by PUT/POST/PATCH).
    """
    try:
        return await _rest_request(method, path, params=params, json_body=json_body)
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_rest_failed", path=path, error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_identity() -> dict:
    """Read the router's system identity (name)."""
    try:
        return await _rest_request("GET", "system/identity")
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_identity_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_system_resource() -> dict:
    """Get RouterOS version, uptime, CPU/board/memory info."""
    try:
        return await _rest_request("GET", "system/resource")
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_resource_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_interfaces() -> dict:
    """List network interfaces and their status."""
    try:
        return await _rest_request("GET", "interface")
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_interfaces_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_ip_addresses() -> dict:
    """List configured IP addresses on the router."""
    try:
        return await _rest_request("GET", "ip/address")
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ip_addresses_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_ping(host: str, count: int = 4) -> dict:
    """Ping a host from the router (via the /tool/ping REST resource).

    Args:
        host: target IP or hostname to ping from the router.
        count: number of ICMP packets. Default 4.
    """
    try:
        body = {"address": host, "count": count}
        return await _rest_request("POST", "ping", json_body=body)
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ping_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
# ---------------------------------------------------------------------------
# SSH (free-form CLI) tools
# ---------------------------------------------------------------------------


async def _run_ssh(command: str, *, timeout: float = 20.0) -> dict[str, Any]:
    settings = get_settings()
    _require_host()
    try:
        import asyncssh
    except ImportError as exc:  # pragma: no cover - guard for optional dep
        return {
            "status": "error",
            "error": "asyncssh is not installed. Run: pip install asyncssh",
            "detail": str(exc),
        }

    try:
        async with asyncssh.connect(
            settings.mikrotik_host,
            port=settings.mikrotik_ssh_port,
            username=settings.mikrotik_user,
            password=settings.mikrotik_password,
            known_hosts=None,
            connect_timeout=10.0,
        ) as conn:
            result = await conn.run(command, check=False, timeout=timeout)
        return {
            "status": "ok",
            "exit_status": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ssh_failed", command=command, error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_ssh_command(command: str, timeout: float = 20.0) -> dict:
    """Run a free-form RouterOS CLI command over SSH.

    Useful for things REST does not cover cleanly, e.g. ``/export``,
    ``/log print`` or ``/tool bandwidth-test``.

    Args:
        command: the RouterOS CLI command line, e.g. "/export".
        timeout: max seconds to wait for the command. Default 20.
    """
    try:
        return await _run_ssh(command, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ssh_command_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_export_config() -> dict:
    """Export the full RouterOS configuration (via SSH ``/export``)."""
    try:
        return await _run_ssh("/export", timeout=60.0)
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_export_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp, default_port=8008)