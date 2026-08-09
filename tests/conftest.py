"""Shared test fixtures.

Strategy:
- Point all DB paths to a temporary directory via env vars BEFORE any settings
  are resolved (pydantic-settings reads env at first Settings() instantiation).
- Replace the real Ollama embedding client with a deterministic fake so tests
  run without an external service.
- Provide a fixture to reset the module-level SQLite connection singletons so
  each test gets a clean database.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Environment setup (session-scoped, runs before any engine import).
# ---------------------------------------------------------------------------

_TMPDIR = tempfile.mkdtemp(prefix="mcp-test-")


@pytest.fixture(scope="session", autouse=True)
def _isolate_environment() -> None:
    """Redirect settings so tests use a throwaway data directory."""
    os.environ["MCP_ROOT"] = _TMPDIR
    os.environ["MEMORY_DB_PATH"] = str(Path(_TMPDIR) / "memory_v2.db")
    os.environ["KNOWLEDGE_DB_PATH"] = str(Path(_TMPDIR) / "knowledge_v2.db")
    # Restrict filesystem tests to the temp dir. pydantic-settings expects
    # complex types (list) to be JSON-encoded in the environment.
    os.environ["ALLOWED_DIRECTORIES"] = json.dumps([_TMPDIR])
    # Ensure no external services are contacted.
    os.environ["REDIS_URL"] = "redis://localhost:1/0"
    os.environ["OLLAMA_URL"] = "http://127.0.0.1:1"
    # Reset the cached settings singleton so env vars take effect.
    import importlib

    _config = importlib.import_module("shared.config")
    _config._settings = None
    yield


# ---------------------------------------------------------------------------
# Engine module accessor (imports submodules explicitly).
# ---------------------------------------------------------------------------


def _get_engine_modules() -> list:
    """Return the SQLite engine modules that hold a module-level ``_db``."""
    from servers.knowledge import engine as knowledge_engine
    from servers.memory import engine as memory_engine
    from servers.skills import engine as skills_engine

    return [memory_engine, knowledge_engine, skills_engine]


# ---------------------------------------------------------------------------
# Fake embedding
# ---------------------------------------------------------------------------


def _fake_embedding(text: str) -> list[float]:
    """Deterministic 768-d vector derived from the input text."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = [((digest[i % 32] + i) % 255) / 255.0 for i in range(768)]
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec]


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Ollama embedding calls with a deterministic local fake.

    The engine modules do ``from shared.embeddings import get_embedding``, which
    binds the function at import time, so we patch it in each engine module (and
    in the shared module for any other importers).
    """
    import shared.embeddings as emb

    async def fake_get_embedding(text: str, *, force_refresh: bool = False) -> list[float]:
        return _fake_embedding(text)

    async def fake_get_embeddings(texts: list[str]) -> list[list[float]]:
        return [_fake_embedding(t) for t in texts]

    patch_targets = [emb] + _get_engine_modules()
    for target in patch_targets:
        if hasattr(target, "get_embedding"):
            monkeypatch.setattr(target, "get_embedding", fake_get_embedding)
        if hasattr(target, "get_embeddings"):
            monkeypatch.setattr(target, "get_embeddings", fake_get_embeddings)


@pytest.fixture(autouse=True)
def _reset_engine_state() -> None:
    """Reset module-level DB singletons and delete DB files.

    The session-scoped temp dir is shared, so without deleting the SQLite files
    data would leak between tests. Removing the files gives each test a clean DB.
    """
    tmp = Path(_TMPDIR)
    for name in ("memory_v2.db", "knowledge_v2.db", "skills_v2.db"):
        for suffix in ("", "-wal", "-shm"):
            f = tmp / f"{name}{suffix}"
            if f.exists():
                f.unlink()
    for mod in _get_engine_modules():
        if hasattr(mod, "_db"):
            mod._db = None  # type: ignore[attr-defined]
    yield
    for mod in _get_engine_modules():
        if hasattr(mod, "_db"):
            mod._db = None  # type: ignore[attr-defined]


@pytest.fixture()
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the cached Settings singleton so env changes take effect.

    Use this fixture in tests that need to override settings via env vars.
    """
    from shared import config as config_mod

    config_mod._settings = None  # type: ignore[attr-defined]


@pytest.fixture()
def allowed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_settings) -> Path:
    """Set ALLOWED_DIRECTORIES to a fresh temp dir and return it."""
    monkeypatch.setenv("ALLOWED_DIRECTORIES", json.dumps([str(tmp_path)]))
    return tmp_path
