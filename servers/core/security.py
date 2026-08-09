"""Security tools exposed via MCP."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from shared.config import get_settings
from shared.security import sanitize_string as _sanitize_string
from shared.security import validate_input as _validate_input


def _audit_path() -> Any:
    from pathlib import Path

    return Path(get_settings().mcp_root) / "logs" / "audit.log"


async def validate_input(value: str, schema_type: str, max_length: int = 1000) -> dict[str, Any]:
    """Validate an input string against a known schema."""
    return _validate_input(value, schema_type, max_length)


async def sanitize_string(text: str, max_length: int = 10_000) -> str:
    """Sanitize a string by removing dangerous characters."""
    return _sanitize_string(text, max_length)


async def audit_log(
    action: str,
    resource: str,
    result: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Append a structured audit entry to the audit log."""
    entry = {
        "id": hashlib.sha256(
            f"{action}:{resource}:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:8],
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action,
        "resource": resource,
        "result": result,
        "metadata": metadata or {},
    }
    log_path = _audit_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry["id"]


async def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Hash a string using sha256, sha512, or md5 (md5 for checksums only)."""
    supported = {"sha256", "sha512", "md5"}
    if algorithm not in supported:
        raise ValueError(f"Unsupported algorithm. Choose one of {supported}")
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()
