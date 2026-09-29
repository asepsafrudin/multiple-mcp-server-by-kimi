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


def _get_connection_info(
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
    router_ssh_port: int | None = None,
) -> tuple[str, int, str, str, str, bool, int]:
    settings = get_settings()

    if router in ("router2", "second", "lokal"):
        base_host = settings.mikrotik2_host
        base_port = settings.mikrotik2_port
        base_scheme = settings.mikrotik2_scheme
        base_user = settings.mikrotik2_user
        base_password = settings.mikrotik2_password
        base_tls_verify = settings.mikrotik2_tls_verify
        base_ssh_port = settings.mikrotik2_ssh_port
        router_err_name = "MIKROTIK2"
    else:
        base_host = settings.mikrotik_host
        base_port = settings.mikrotik_port
        base_scheme = settings.mikrotik_scheme
        base_user = settings.mikrotik_user
        base_password = settings.mikrotik_password
        base_tls_verify = settings.mikrotik_tls_verify
        base_ssh_port = settings.mikrotik_ssh_port
        router_err_name = "MIKROTIK"

    final_host = router_host if router_host is not None else base_host
    final_port = router_port if router_port is not None else base_port
    final_scheme = router_scheme if router_scheme is not None else base_scheme
    final_user = router_user if router_user is not None else base_user
    final_password = router_password if router_password is not None else base_password
    final_tls_verify = router_tls_verify if router_tls_verify is not None else base_tls_verify
    final_ssh_port = router_ssh_port if router_ssh_port is not None else base_ssh_port

    if not final_host:
        raise RuntimeError(
            f"{router_err_name}_HOST not configured. Set suitable variables in .env."
        )

    return (
        final_host,
        final_port,
        final_scheme,
        final_user or "",
        final_password or "",
        final_tls_verify,
        final_ssh_port,
    )


async def _rest_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict[str, Any]:
    final_host, final_port, final_scheme, final_user, final_password, final_tls_verify, _ = (
        _get_connection_info(
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    )
    url = f"{final_scheme}://{final_host}:{final_port}/rest/{path.lstrip('/')}"
    async with httpx.AsyncClient(
        auth=httpx.BasicAuth(final_user, final_password),
        timeout=30.0,
        verify=final_tls_verify,
    ) as client:
        response = await client.request(method.upper(), url, params=params, json=json_body)
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
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """Call an arbitrary RouterOS REST endpoint.

    Args:
        path: resource path without a leading slash, e.g. "interface",
            "ip/address", "system/identity" or "tool/ping".
        method: HTTP method (GET, PUT, POST, PATCH, DELETE). Default "GET".
        params: optional query-string parameters.
        json_body: optional JSON payload (used by PUT/POST/PATCH).
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        return await _rest_request(
            method,
            path,
            params=params,
            json_body=json_body,
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_rest_failed", path=path, error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_identity(
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """Read the router's system identity (name).

    Args:
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        return await _rest_request(
            "GET",
            "system/identity",
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_identity_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_system_resource(
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """Get RouterOS version, uptime, CPU/board/memory info.

    Args:
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        return await _rest_request(
            "GET",
            "system/resource",
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_resource_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_interfaces(
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """List network interfaces and their status.

    Args:
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        return await _rest_request(
            "GET",
            "interface",
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_interfaces_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_get_ip_addresses(
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """List configured IP addresses on the router.

    Args:
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        return await _rest_request(
            "GET",
            "ip/address",
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ip_addresses_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_ping(
    host: str,
    count: int = 4,
    router: str = "default",
    router_host: str | None = None,
    router_port: int | None = None,
    router_scheme: str | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
    router_tls_verify: bool | None = None,
) -> dict:
    """Ping a host from the router (via the /tool/ping REST resource).

    Args:
        host: target IP or hostname to ping from the router.
        count: number of ICMP packets. Default 4.
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_port: dynamic override for REST port.
        router_scheme: dynamic override for URI scheme (http or https).
        router_user: dynamic override for username.
        router_password: dynamic override for password.
        router_tls_verify: dynamic override for TLS verification.
    """
    try:
        body = {"address": host, "count": count}
        return await _rest_request(
            "POST",
            "ping",
            json_body=body,
            router=router,
            router_host=router_host,
            router_port=router_port,
            router_scheme=router_scheme,
            router_user=router_user,
            router_password=router_password,
            router_tls_verify=router_tls_verify,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ping_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# SSH (free-form CLI) tools
# ---------------------------------------------------------------------------


async def _run_ssh(
    command: str,
    *,
    timeout: float = 20.0,
    router: str = "default",
    router_host: str | None = None,
    router_ssh_port: int | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
) -> dict[str, Any]:
    try:
        import asyncssh
    except ImportError as exc:  # pragma: no cover - guard for optional dep
        return {
            "status": "error",
            "error": "asyncssh is not installed. Run: pip install asyncssh",
            "detail": str(exc),
        }

    final_host, _, _, final_user, final_password, _, final_ssh_port = _get_connection_info(
        router=router,
        router_host=router_host,
        router_user=router_user,
        router_password=router_password,
        router_ssh_port=router_ssh_port,
    )

    try:
        async with asyncssh.connect(
            final_host,
            port=final_ssh_port,
            username=final_user,
            password=final_password,
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
async def mikrotik_ssh_command(
    command: str,
    timeout: float = 20.0,
    router: str = "default",
    router_host: str | None = None,
    router_ssh_port: int | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
) -> dict:
    """Run a free-form RouterOS CLI command over SSH.

    Useful for things REST does not cover cleanly, e.g. ``/export``,
    ``/log print`` or ``/tool bandwidth-test``.

    Args:
        command: the RouterOS CLI command line, e.g. "/export".
        timeout: max seconds to wait for the command. Default 20.
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_ssh_port: dynamic override for SSH port.
        router_user: dynamic override for username.
        router_password: dynamic override for password.
    """
    try:
        return await _run_ssh(
            command,
            timeout=timeout,
            router=router,
            router_host=router_host,
            router_ssh_port=router_ssh_port,
            router_user=router_user,
            router_password=router_password,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_ssh_command_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def mikrotik_export_config(
    router: str = "default",
    router_host: str | None = None,
    router_ssh_port: int | None = None,
    router_user: str | None = None,
    router_password: str | None = None,
) -> dict:
    """Export the full RouterOS configuration (via SSH ``/export``).

    Args:
        router: router profile to use ('default' or 'router2'). Default 'default'.
        router_host: dynamic override for router host/ip.
        router_ssh_port: dynamic override for SSH port.
        router_user: dynamic override for username.
        router_password: dynamic override for password.
    """
    try:
        return await _run_ssh(
            "/export",
            timeout=60.0,
            router=router,
            router_host=router_host,
            router_ssh_port=router_ssh_port,
            router_user=router_user,
            router_password=router_password,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("mikrotik_export_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    from shared.server_runner import run

    run(mcp, default_port=8008)
