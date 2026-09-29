"""Tests for TASK-143 fail-fast behaviour of the Orchestrator server.

These tests verify that the orchestrator refuses to start (exits non-zero)
when required dependencies or environment variables are missing, instead of
silently falling back to a non-functional mock.

Run with: pytest tests/test_orchestrator_fail_fast.py -v
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_MAIN = REPO_ROOT / "servers" / "orchestrator" / "main.py"


def _reload_orchestrator() -> None:
    """Drop cached orchestrator modules so the next import re-runs module code."""
    for mod_name in list(sys.modules):
        if mod_name.startswith("servers.orchestrator"):
            sys.modules.pop(mod_name, None)


class TestPreflightCheck:
    """Unit tests for the preflight_check() function."""

    def test_preflight_passes_with_ollama_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """preflight_check() should succeed when OPENAI_BASE_URL points to local Ollama."""
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
        # OPENAI_API_KEY is auto-set to 'ollama' by preflight for local Ollama.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from servers.orchestrator.main import preflight_check

        preflight_check()
        assert os.environ["OPENAI_API_KEY"] == "ollama"

    def test_preflight_fails_when_remote_base_url_missing_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If using a hosted provider (non-localhost), OPENAI_API_KEY is required."""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from servers.orchestrator.main import preflight_check

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            preflight_check()

    @pytest.mark.parametrize(
        "bad_url",
        ["not-a-url", "ftp://example.com/v1", "http://", ":11434/v1"],
    )
    def test_preflight_rejects_malformed_base_url(
        self, monkeypatch: pytest.MonkeyPatch, bad_url: str
    ) -> None:
        """A malformed OPENAI_BASE_URL must fail fast, not fail later at call time."""
        monkeypatch.setenv("OPENAI_BASE_URL", bad_url)
        monkeypatch.setenv("OPENAI_API_KEY", "irrelevant")

        from servers.orchestrator.main import preflight_check

        with pytest.raises(RuntimeError, match="OPENAI_BASE_URL"):
            preflight_check()


class TestDependencyImportFailFast:
    """Verify the orchestrator raises RuntimeError when agent_framework is missing."""

    def test_import_error_raises_runtime_error_without_allow_mock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without ALLOW_MOCK_FALLBACK, missing agent_framework -> RuntimeError."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "agent_framework" or name.startswith("agent_framework."):
                raise ImportError(f"simulated missing {name}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        monkeypatch.delenv("ALLOW_MOCK_FALLBACK", raising=False)
        _reload_orchestrator()

        with pytest.raises(RuntimeError, match="agent_framework is required"):
            importlib.import_module("servers.orchestrator.main")

    def test_allow_mock_fallback_restores_legacy_behaviour(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ALLOW_MOCK_FALLBACK=1, the legacy mock is allowed (but loud warning)."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "agent_framework" or name.startswith("agent_framework."):
                raise ImportError(f"simulated missing {name}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        monkeypatch.setenv("ALLOW_MOCK_FALLBACK", "1")
        _reload_orchestrator()

        # Should NOT raise - falls back to the legacy mock with a stderr warning.
        importlib.import_module("servers.orchestrator.main")


class TestMainEntryPointExitCode:
    """Verify main() exits with non-zero code on startup failure."""

    def test_main_exits_nonzero_on_preflight_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() must exit with code 1 if preflight_check fails."""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.invalid-provider.example/v1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _reload_orchestrator()

        from servers.orchestrator import main as orch_main

        with pytest.raises(SystemExit) as exc_info:
            orch_main.main()
        assert exc_info.value.code == 1


@pytest.mark.skipif(
    not ORCHESTRATOR_MAIN.exists(),
    reason="orchestrator main.py not present",
)
class TestCliIntegration:
    """Subprocess test verifying the process-level exit code on import failure."""

    # Bootstraps a subprocess in which `import agent_framework` raises, then
    # executes the real module. Simply clearing PYTHONPATH is NOT enough to
    # simulate a missing dependency, because site-packages stays on sys.path.
    _BOOTSTRAP = (
        "import builtins, sys\n"
        "_real_import = builtins.__import__\n"
        "def _fake_import(name, *args, **kwargs):\n"
        "    if name == 'agent_framework' or name.startswith('agent_framework.'):\n"
        "        raise ImportError('simulated missing ' + name)\n"
        "    return _real_import(name, *args, **kwargs)\n"
        "builtins.__import__ = _fake_import\n"
        "path = sys.argv[1]\n"
        "source = open(path, encoding='utf-8').read()\n"
        "exec(compile(source, path, 'exec'), {'__name__': '__main__', '__file__': path})\n"
    )

    def test_import_failure_exits_nonzero(self) -> None:
        """Launching the module without agent_framework must exit non-zero."""
        env = os.environ.copy()
        env.pop("ALLOW_MOCK_FALLBACK", None)

        result = subprocess.run(
            [sys.executable, "-c", self._BOOTSTRAP, str(ORCHESTRATOR_MAIN)],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )

        assert result.returncode != 0, f"expected failure, got 0. stderr={result.stderr!r}"
        assert "agent_framework is required" in result.stderr
