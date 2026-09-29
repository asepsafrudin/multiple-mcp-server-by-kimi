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


class TestPreflightCheck:
    """Unit tests for the preflight_check() function."""

    def test_preflight_passes_with_ollama_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """preflight_check() should succeed when OPENAI_BASE_URL points to local Ollama."""
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
        # OPENAI_API_KEY auto-set to 'ollama' by preflight when local Ollama is detected
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from servers.orchestrator.main import preflight_check

        # Should not raise
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


class TestDependencyImportFailFast:
    """Verify the orchestrator raises RuntimeError when agent_framework is missing."""

    def test_import_error_raises_runtime_error_without_allow_mock(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Without ALLOW_MOCK_FALLBACK, missing agent_framework -> RuntimeError."""
        # Simulate missing agent_framework
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "agent_framework" or name.startswith("agent_framework."):
                raise ImportError(f"simulated missing {name}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        monkeypatch.delenv("ALLOW_MOCK_FALLBACK", raising=False)

        # Force a fresh import of orchestrator.main
        for mod_name in list(sys.modules):
            if mod_name.startswith("servers.orchestrator"):
                sys.modules.pop(mod_name, None)

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

        for mod_name in list(sys.modules):
            if mod_name.startswith("servers.orchestrator"):
                sys.modules.pop(mod_name, None)

        # Should NOT raise - falls back to legacy mock with warning
        importlib.import_module("servers.orchestrator.main")


class TestMainEntryPointExitCode:
    """Verify main() exits with non-zero code on startup failure."""

    def test_main_exits_nonzero_on_preflight_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() must exit with code 1 if preflight_check fails."""
        # Force preflight failure by pointing to remote base without API key
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.invalid-provider.example/v1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        for mod_name in list(sys.modules):
            if mod_name.startswith("servers.orchestrator"):
                sys.modules.pop(mod_name, None)

        from servers.orchestrator import main as orch_main

        with pytest.raises(SystemExit) as exc_info:
            orch_main.main()
        assert exc_info.value.code == 1


@pytest.mark.skipif(
    not ORCHESTRATOR_MAIN.exists(),
    reason="orchestrator main.py not present",
)
class TestCliIntegration:
    """Subprocess tests verifying actual CLI behaviour."""

    def test_missing_dependency_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Subprocess invocation should exit non-zero when deps missing."""
        env = os.environ.copy()
        env.pop("ALLOW_MOCK_FALLBACK", None)
        # Strip agent_framework from PYTHONPATH to force ImportError
        env["PYTHONPATH"] = "/nonexistent"

        result = subprocess.run(
            [sys.executable, str(ORCHESTRATOR_MAIN)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        # Either: imports fail at top level -> non-zero exit
        # Or: agent_framework missing -> RuntimeError raised -> non-zero exit
        assert result.returncode != 0
        assert "agent_framework" in result.stderr or "ImportError" in result.stderr
