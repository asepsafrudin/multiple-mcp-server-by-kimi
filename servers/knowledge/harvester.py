"""Workspace knowledge harvester: scan, chunk, embed and index files."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from shared.config import get_settings
from shared.logging import get_logger
from shared.models import KnowledgeChunk
from servers.knowledge.chunking import chunk_file
from servers.knowledge.engine import index_chunks

logger = get_logger("mcp.knowledge.harvester")

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".html", ".htm", ".css", ".scss", ".less",
    ".sql", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".java",
    ".rb", ".php", ".swift", ".kt", ".kts", ".cs", ".fs",
    ".xml", ".svg", ".graphql", ".prisma",
}

IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv",
    "venv", "env", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "target", ".next", ".nuxt", ".idea", ".vscode",
    "coverage", ".coverage", "htmlcov", "site-packages", "egg-info",
}

IGNORED_FILES = {
    ".env", ".env.local", ".env.production", ".envrc", ".pnp.js",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "Gemfile.lock", "composer.lock",
}


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("text/"):
        return True
    return False


def _should_skip(path: Path) -> bool:
    if any(part in IGNORED_DIRS for part in path.parts):
        return True
    if path.name in IGNORED_FILES:
        return True
    if path.name.startswith(".") and path.suffix in {".pyc", ".pyo", ".so", ".dylib", ".dll"}:
        return True
    return False


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:32]


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def _read_text(path: Path, max_bytes: int = 2 * 1024 * 1024) -> str | None:
    try:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            logger.warning("file_too_large", path=str(path), size=len(raw))
            return None
        # Skip likely binary files.
        if b"\x00" in raw[:4096]:
            return None
        return raw.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("read_failed", path=str(path), error=str(exc))
        return None


async def harvest_project(
    project: str,
    root: Path | None = None,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Harvest a workspace project into searchable knowledge chunks."""
    settings = get_settings()
    root = root or settings.workspace_root / project
    max_files = max_files or settings.knowledge_max_files_per_run

    if not root.exists():
        return {"error": f"Project root not found: {root}"}

    files_scanned = 0
    files_indexed = 0
    chunks_total = 0
    all_chunks: list[KnowledgeChunk] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path):
            continue
        if not _is_text_file(path):
            continue
        if files_scanned >= max_files:
            logger.info("max_files_reached", project=project, limit=max_files)
            break

        files_scanned += 1
        text = _read_text(path)
        if text is None:
            continue

        content_bytes = text.encode("utf-8", errors="replace")
        file_hash = _file_hash(content_bytes)
        rel_path = str(path.relative_to(root))
        file_type = _file_type(path)

        chunks = chunk_file(path, text)
        total = len(chunks)
        for idx, chunk_text in enumerate(chunks):
            all_chunks.append(
                KnowledgeChunk(
                    project=project,
                    file_path=rel_path,
                    file_hash=file_hash,
                    file_type=file_type,
                    chunk_index=idx,
                    total_chunks=total,
                    content=chunk_text,
                    metadata={"size_bytes": len(content_bytes)},
                )
            )

        files_indexed += 1
        chunks_total += total

        # Batch insert every N chunks to bound memory.
        if len(all_chunks) >= 200:
            result = await index_chunks(all_chunks)
            if result.get("error"):
                return {"error": result["error"], "indexed_so_far": chunks_total}
            all_chunks = []

    if all_chunks:
        result = await index_chunks(all_chunks)
        if result.get("error"):
            return {"error": result["error"], "indexed_so_far": chunks_total}

    return {
        "project": project,
        "root": str(root),
        "files_scanned": files_scanned,
        "files_indexed": files_indexed,
        "chunks_indexed": chunks_total,
    }
