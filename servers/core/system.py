"""System information and environment utilities."""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from typing import Any

import psutil


async def get_system_info() -> dict[str, Any]:
    """Return basic host system statistics."""
    mem = psutil.virtual_memory()
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "os": platform.system(),
        "os_version": platform.release(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_percent": mem.percent,
        "cwd": os.getcwd(),
        "python_version": platform.python_version(),
    }


async def get_env_variable(name: str) -> dict[str, Any]:
    """Read a non-sensitive environment variable."""
    value = os.environ.get(name)
    if value is None:
        return {"found": False, "value": None}

    # Basic guard: never return values that look like API keys or passwords.
    lowered = name.lower()
    sensitive_keys = {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "credential",
    }
    if any(k in lowered for k in sensitive_keys):
        return {"found": True, "value": "<redacted>", "note": "Sensitive key redacted"}

    return {"found": True, "value": value}
