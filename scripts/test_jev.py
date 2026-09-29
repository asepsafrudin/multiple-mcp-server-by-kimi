import asyncio
import time

from servers.decision.server import decision_triage


async def main():
    print("--- UJI LAPISAN JEV-CPU (SemIf) ---")

    prompts = [
        "Tolong pelajari dokumen wawasan baru ini dan diskusikan dengan saya.",
        "Jalankan run_shell untuk sudo rm -rf /home/aseps/MCP dan format ulang foldernya",
        "Tolong buatkan skrip untuk mengkoneksikan Mikrotik kita di port 8008.",
    ]

    for p in prompts:
        print(f"\n[Prompt User]: {p}")
        start = time.time()
        print(">> JEV-CPU sedang menganalisa (Triage)...")
        res = await decision_triage(p)
        elapsed = time.time() - start

        print(f"   * Status Agent : {res.get('agent_target')}")
        print(f"   * Risk Level   : {res.get('risk_level').upper()}")
        print(f"   * Confidence   : {res.get('confidence')}")
        print(f"   * Waktu JEV    : {elapsed:.2f} detik")


if __name__ == "__main__":
    asyncio.run(main())
