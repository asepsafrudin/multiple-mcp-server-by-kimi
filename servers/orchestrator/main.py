"""Orchestrator MAF (Master Agentic Framework) Server — fail-fast, no silent fallback.

TASK-143 — Audit Top 10 Critical Finding #1.

Previous behaviour (BUG): if `agent_framework` was missing, the server fell back
to mock classes that silently swallowed every request (no error, no log, no
response). This caused data corruption in production because clients received
"successful" responses that contained no real result.

New behaviour (FIX): the orchestrator now FAIL-FAST. If any required dependency
or environment variable is missing, the process exits with a clear error
message before binding the stdio transport.

Backward compatibility: set `ALLOW_MOCK_FALLBACK=1` to restore the legacy
mock behaviour. Default is OFF. This is intended only for local development
and tests; production deployments MUST run without the env var.
"""

from __future__ import annotations

import asyncio
import os
import sys


def _maybe_mock_dependencies() -> tuple[type, type, type]:
    """Return (Agent, MCPStreamableHTTPTool, OpenAIChatClient) — either real or legacy mock.

    Returns the real classes from `agent_framework` if available. If the import
    fails AND the operator explicitly opted in to legacy behaviour via the
    `ALLOW_MOCK_FALLBACK=1` environment variable, returns the deprecated mock
    classes and prints a loud warning to stderr. Otherwise raises RuntimeError
    so the orchestrator exits non-zero at startup.

    Raises:
        RuntimeError: if `agent_framework` is missing and ALLOW_MOCK_FALLBACK is not set.
    """
    try:
        from agent_framework import Agent, MCPStreamableHTTPTool  # type: ignore[import-not-found]
        from agent_framework.openai import OpenAIChatClient  # type: ignore[import-not-found]

        return Agent, MCPStreamableHTTPTool, OpenAIChatClient
    except ImportError as exc:
        if os.environ.get("ALLOW_MOCK_FALLBACK") == "1":
            sys.stderr.write(
                "WARNING: ALLOW_MOCK_FALLBACK=1 — using LEGACY mock classes. "
                "Server will not respond to requests. This mode is DEPRECATED and "
                "will be removed in v1.0. See TASK-143.\n"
            )

            class MCPStreamableHTTPTool:  # type: ignore[no-redef]
                def __init__(self, name: str, url: str) -> None:
                    self.name = name
                    self.url = url

            class OpenAIChatClient:  # type: ignore[no-redef]
                pass

            class Agent:  # type: ignore[no-redef]
                def __init__(
                    self,
                    client: object,
                    name: str,
                    instructions: str,
                    tools: list[object],
                ) -> None:
                    self.client = client
                    self.name = name
                    self.instructions = instructions
                    self.tools = tools

                def as_mcp_server(self) -> object:
                    class MockServer:
                        def create_initialization_options(self) -> dict[str, object]:
                            return {}

                        async def run(
                            self,
                            r: object,
                            w: object,
                            options: object,
                        ) -> None:
                            # Legacy silent fallback — kept only for backward
                            # compatibility under ALLOW_MOCK_FALLBACK=1.
                            return None

                    return MockServer()

            return Agent, MCPStreamableHTTPTool, OpenAIChatClient

        raise RuntimeError(
            "agent_framework is required but not installed.\n"
            "Install with one of:\n"
            "  pip install -e \".[agents]\"   (uses pyproject.toml extras)\n"
            "  pip install agent-framework\n"
            f"Original ImportError: {exc}\n"
            "If you intentionally want the legacy silent mock for local dev, "
            "set ALLOW_MOCK_FALLBACK=1 (deprecated, will be removed in v1.0)."
        ) from exc


# Resolve dependencies once at module import — fail-fast at startup, not per-request.
Agent, MCPStreamableHTTPTool, OpenAIChatClient = _maybe_mock_dependencies()


def preflight_check() -> None:
    """Verify all required environment variables are set before server start.

    Raises:
        RuntimeError: if any required environment variable is missing.
    """
    required: dict[str, str] = {
        # Ollama default is acceptable for local dev. For hosted providers,
        # operators must set the corresponding key (e.g. OPENAI_API_KEY).
        "OPENAI_API_KEY": (
            "Chat model API key. For local Ollama set to 'ollama'. "
            "For hosted providers set the provider-specific key."
        ),
    }

    # If using Ollama locally, OPENAI_API_KEY is not strictly required.
    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
    if "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
        # Local Ollama — API key may be any non-empty placeholder.
        if not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = "ollama"

    missing = [(k, desc) for k, desc in required.items() if not os.environ.get(k)]
    if missing:
        details = "\n".join(f"  - {k}: {desc}" for k, desc in missing)
        raise RuntimeError(
            f"Orchestrator preflight failed. Missing environment variables:\n{details}\n"
            "Copy .env.example to .env and set the required values, then retry."
        )


async def run_maf_server() -> None:
    """Menjalankan Orchestrator agen MAF menggunakan koneksi stdio."""

    # Run preflight checks first — fail-fast at startup, not per-request.
    preflight_check()

    # Import stdio_server AFTER preflight so we don't bind the transport if
    # configuration is invalid. This keeps error reporting on stderr clean.
    from mcp.server.stdio import stdio_server

    # Inisialisasi Tools untuk connect ke server eksisting (SSE)
    # Server kita jalan di port tersebut sesuai skema
    tools = [
        MCPStreamableHTTPTool(name="memory", url="http://127.0.0.1:8001/sse"),
        MCPStreamableHTTPTool(name="knowledge", url="http://127.0.0.1:8002/sse"),
        MCPStreamableHTTPTool(name="skills", url="http://127.0.0.1:8003/sse"),
        MCPStreamableHTTPTool(name="bridge_gmail", url="http://127.0.0.1:8004/sse"),
        MCPStreamableHTTPTool(name="bridge_telegram", url="http://127.0.0.1:8005/sse"),
        MCPStreamableHTTPTool(name="bridge_gemini", url="http://127.0.0.1:8006/sse"),
        MCPStreamableHTTPTool(name="bridge_vision", url="http://127.0.0.1:8007/sse"),
        MCPStreamableHTTPTool(name="bridge_mikrotik", url="http://127.0.0.1:8008/sse"),
        # Lapisan Keputusan (SemIf / JEV-CPU) berjalan di CPU
        MCPStreamableHTTPTool(name="semif_decision", url="http://127.0.0.1:8080/mcp"),
    ]

    # Inisiasi MAF Agent (Lapisan 1: Orkestrasi)
    agent = Agent(
        client=OpenAIChatClient(
            model=os.environ.get("ORCHESTRATOR_MODEL", "llama3.2"),
            base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ["OPENAI_API_KEY"],
        ),
        name="MAF_Orchestrator",
        instructions=(
            "Anda adalah node Orchestrator (MAF) di puncak Arsitektur 5-Lapis.\n"
            "Alur kerja Anda (Triage -> Coding -> Hindsight):\n"
            "1. Triage: Panggil 'semif_decision' untuk routing, guardrails, & klasifikasi "
            "tugas awal. Jika Qwen3-0.6B ragu (confidence < 0.5), eskalasi ke Human-in-the-loop.\n"
            "2. Memori: Akses Hindsight Memory melalui server 'memory' (retain, reflect, "
            "search_advice) untuk memanggil Mental Models & Observations.\n"
            "3. Execution: Delegasikan instruksi koding kepada `smolagents CodeAgent` murni "
            "via run_shell python atau serahkan pada e2b sandbox. Panduan cara koding dapat "
            "dibaca dari folder `skills/` (Hugging Face SKILL.md). Gunakan MCP Bridge untuk "
            "kapabilitas eksternal (Mis. MikroTik)."
        ),
        tools=tools,
    )

    # Bungkus sebagai MCP Server
    server = agent.as_mcp_server()

    # Startup banner — useful for log-based detection of orchestrator readiness.
    sys.stderr.write(
        f"[MAF_Orchestrator] starting: model={os.environ.get('ORCHESTRATOR_MODEL', 'llama3.2')}, "
        f"tools={len(tools)}, mock_fallback={'on' if os.environ.get('ALLOW_MOCK_FALLBACK') == '1' else 'off'}\n"
    )

    # Jalankan stdio loop
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point — convert startup failures into non-zero exit codes."""
    try:
        asyncio.run(run_maf_server())
    except RuntimeError as exc:
        sys.stderr.write(f"FATAL: Orchestrator failed to start: {exc}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("[MAF_Orchestrator] interrupted, shutting down.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
