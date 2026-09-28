"""Security primitives: safe path resolution and input sanitisation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared.config import get_settings


def resolve_allowed_directories() -> list[Path]:
    return [Path(d).expanduser().resolve() for d in get_settings().allowed_directories]


def _is_within(candidate: Path, allowed: list[Path]) -> bool:
    """Return True when ``candidate`` is one of ``allowed`` or a descendant of one.

    String based checks (``str(candidate).startswith(str(root))``) are unsafe:
    a sibling directory such as ``/data/allowed-evil`` shares the ``/data/allowed``
    prefix and would be accepted. ``Path.is_relative_to`` compares real path
    components, so the ``==`` case is handled explicitly here.
    """
    return any(candidate == root or candidate.is_relative_to(root) for root in allowed)


def is_path_allowed(path: str | Path) -> bool:
    """Resolve ``path`` and check it against the configured allowed directories."""
    return _is_within(Path(path).expanduser().resolve(), resolve_allowed_directories())


class UnsafePathError(ValueError):
    """Raised when a path escapes the configured allowed directories."""


class SafePath:
    """A path that has been validated against the allowed directory list."""

    def __init__(self, path: str | Path) -> None:
        raw = str(path)
        if ".." in Path(raw).parts:
            raise UnsafePathError(f"Path traversal not allowed: {raw}")

        resolved = Path(raw).expanduser().resolve()
        if not _is_within(resolved, resolve_allowed_directories()):
            raise UnsafePathError(f"Access to path not allowed: {raw}")

        self.path = resolved
        self.raw = raw

    def __str__(self) -> str:
        return str(self.path)

    def __fspath__(self) -> str:
        return str(self.path)


# Character sets that are frequently used in injection / XSS.
_UNSAFE_CHARS_RE = re.compile(r"[<>\"';&|`$\\]")


def sanitize_string(text: str, max_length: int = 10_000) -> str:
    """Remove dangerous characters and collapse whitespace."""
    if len(text) > max_length:
        text = text[:max_length]
    text = _UNSAFE_CHARS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Keep patterns lightweight; callers can enforce stricter validation.
_INPUT_PATTERNS = {
    "email": re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"),
    "uuid": re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    ),
    "alphanumeric": re.compile(r"^[a-zA-Z0-9_\-]+$"),
    "safe_string": re.compile(r"^[^<>\"';&|`$\\]+$"),
    "url": re.compile(r"^https?://[^\s/$.?#].[^\s]*$"),
}


def validate_input(value: str, schema_type: str, max_length: int = 1000) -> dict[str, Any]:
    if schema_type not in _INPUT_PATTERNS:
        return {"valid": False, "error": f"Unknown schema_type: {schema_type}"}
    if len(value) > max_length:
        return {"valid": False, "error": f"Length exceeds {max_length}"}
    ok = bool(_INPUT_PATTERNS[schema_type].match(value))
    return {"valid": ok, "error": None if ok else f"Does not match {schema_type}"}
