"""MCP SemIf (JEV-CPU) Decision Server entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import time

from fastmcp import FastMCP

from shared.logging import configure_logging

configure_logging()

mcp = FastMCP(
    name="mcp-decision-server",
    instructions=(
        "Node keputusan SemIf. Lakukan triage, berikan level keamanan, "
        "dan skor kepastian (confidence) sebelum task diberikan ke Orchestrator."
    ),
)

# Placeholder untuk model ringan (Qwen3-0.6B) yang akan jalan murni di CPU.
# Untuk saat ini, menggunakan heuristik simulasi latensi (1.1 - 1.2 detik)
# dan memanggil Ollama fallback bila dibutuhkan.


@mcp.tool()
async def decision_triage(task_description: str) -> dict:
    """
    Menganalisis instruksi/tugas dan mengembalikan klasifikasi, tipe routing agen,
    dan confidence score. Sangat cepat (~1.1s).
    """
    start_time = time.time()

    # 1. Deteksi heuristik/routing (MOCK Qwen3-0.6B CPU Inference)
    description_lower = task_description.lower()

    agent_target = "omp_coding_agent"
    risk_level = "low"
    confidence = 0.85
    needs_clarification = False
    clarification_questions = []

    # Deteksi ambiguitas jika instruksi terlalu pendek atau kurang spesifik
    if (
        len(description_lower.split()) < 5
        or "buat web" in description_lower
        or "bikin aplikasi" in description_lower
    ):
        confidence = 0.4
        needs_clarification = True
        clarification_questions.append(
            "Framework Frontend apa yang ingin Anda gunakan? (misal: React Vite, Svelte, Vue)?"
        )
        clarification_questions.append(
            "Teknologi Backend/Database apa yang Anda preferensikan? (misal: FastAPI, Node.js, SQLite/PostgreSQL)?"
        )
        agent_target = "human_escalation"

    elif any(
        keyword in description_lower
        for keyword in ["rm -rf", "delete database", "drop table", "format"]
    ):
        risk_level = "high"
        confidence = 0.99
        agent_target = "human_escalation"

    elif any(keyword in description_lower for keyword in ["review", "check pr", "audit"]):
        agent_target = "maf_review_agent"
        confidence = 0.92

    elif any(
        keyword in description_lower for keyword in ["routeros", "mikrotik", "gmail", "telegram"]
    ):
        agent_target = "mcp_bridge_agent"
        confidence = 0.88

    # Delay simulasi beban proses inference JEV-CPU (1.1 detik)
    time.sleep(1.1)

    latency = time.time() - start_time

    return {
        "status": "clarification_needed" if needs_clarification else "triaged",
        "agent_target": agent_target,
        "risk_level": risk_level,
        "confidence": confidence,
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "latency_seconds": round(latency, 2),
        "model": "qwen3-0.6b-cpu-emulated",
    }


if __name__ == "__main__":
    from shared.server_runner import run

    # Standar port untuk decision (SemIf) adalah 8080 di Arsitektur
    run(mcp)
