"""Filesystem tools with path sandboxing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.config import get_settings
from shared.security import SafePath, UnsafePathError


def _check_size(path: Path) -> None:
    max_bytes = get_settings().max_file_size_mb * 1024 * 1024
    if path.is_file() and path.stat().st_size > max_bytes:
        raise ValueError(
            f"File too large: {path.stat().st_size / (1024 * 1024):.1f}MB "
            f"(max {get_settings().max_file_size_mb}MB)"
        )


async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a text file from an allowed directory."""
    safe = SafePath(path)
    if not safe.path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not safe.path.is_file():
        raise ValueError(f"Not a file: {path}")
    _check_size(safe.path)
    return safe.path.read_text(encoding=encoding)


async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write text to a file inside an allowed directory."""
    safe = SafePath(path)
    safe.path.parent.mkdir(parents=True, exist_ok=True)
    safe.path.write_text(content, encoding=encoding)
    size = len(content.encode(encoding))
    return f"Wrote {size} bytes to {safe.path}"


async def list_directory(
    path: str = ".", show_hidden: bool = False
) -> list[dict[str, Any]]:
    """List directory contents with basic metadata."""
    safe = SafePath(path)
    if not safe.path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    items: list[dict[str, Any]] = []
    for entry in sorted(safe.path.iterdir()):
        if not show_hidden and entry.name.startswith("."):
            continue
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size_bytes": stat.st_size if entry.is_file() else None,
                "modified": stat.st_mtime,
            }
        )
    return items


async def search_files(
    directory: str, pattern: str, recursive: bool = True, max_results: int = 50
) -> list[str]:
    """Search files by glob pattern inside an allowed directory."""
    safe = SafePath(directory)
    if not safe.path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    method = safe.path.rglob if recursive else safe.path.glob
    results = [str(f) for f in method(pattern) if f.is_file()]
    return results[:max_results]


async def delete_file(path: str) -> str:
    """Delete a file. This operation is irreversible."""
    safe = SafePath(path)
    if not safe.path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not safe.path.is_file():
        raise ValueError(f"Not a file: {path}")
    safe.path.unlink()
    return f"Deleted: {safe.path}"


async def move_file(source: str, destination: str) -> str:
    """Move or rename a file within allowed directories."""
    safe_src = SafePath(source)
    safe_dst = SafePath(destination)
    if not safe_src.path.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    safe_dst.path.parent.mkdir(parents=True, exist_ok=True)
    safe_src.path.rename(safe_dst.path)
    return f"Moved {safe_src.path} -> {safe_dst.path}"
