#!/usr/bin/env python3
"""
harvest_daily.py — Daily Knowledge Harvest dari Workspace
===========================================================
Script ini dijalankan harian via cron untuk:
1. Index file-file baru/berubah dari Workspace (incremental)
2. Kirim "Daily Digest" ke Telegram: statistik + hal-hal baru
3. Cleanup: hapus chunks dari file yang sudah dihapus

Setup cron (jalankan setiap malam jam 23:00):
    0 23 * * * /home/aseps/MCP/.venv/bin/python3 /home/aseps/MCP/scripts/harvest_daily.py >> /home/aseps/MCP/logs/harvest_daily.log 2>&1
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP")

# Load env
env_file = Path("/home/aseps/MCP/config/.env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("harvest-daily")


async def main():
    from mcp_unified.intelligence.knowledge_harvester import harvest_directory_async, harvest_status

    start_time = datetime.now()
    logger.info(f"=== Daily Harvest dimulai: {start_time.strftime('%Y-%m-%d %H:%M')} ===")

    # --- Fase 1: Harvest file teks & code (cepat) ---
    logger.info("Fase 1: Harvest dokumen teks & code...")
    text_result = await harvest_directory_async(
        directory="/home/aseps/Workspace",
        max_files=300,
        extensions=[".md", ".txt", ".py", ".sql", ".sh", ".csv", ".json"],
        force=False  # Skip yang sudah terindeks
    )

    # --- Fase 2: Harvest PDF area tertentu yang paling penting ---
    logger.info("Fase 2: Harvest PDF dari Data/...")
    pdf_result = await harvest_directory_async(
        directory="/home/aseps/Workspace/Data",
        max_files=100,
        extensions=[".pdf"],
        force=False
    )

    # --- Kirim Daily Digest ke Telegram ---
    total_indexed = text_result.get("indexed", 0) + pdf_result.get("indexed", 0)
    total_skipped = text_result.get("skipped", 0) + pdf_result.get("skipped", 0)
    projects = list(set(
        text_result.get("projects_touched", []) +
        pdf_result.get("projects_touched", [])
    ))
    elapsed = text_result.get("elapsed_seconds", 0) + pdf_result.get("elapsed_seconds", 0)

    status = harvest_status({})
    total_files_in_db = status.get("summary", {}).get("total_files_indexed", 0)
    total_chunks = status.get("summary", {}).get("total_chunks", 0)

    digest_message = (
        f"🌙 <b>Daily Knowledge Digest</b>\n"
        f"📅 {start_time.strftime('%d %B %Y')} — {start_time.strftime('%H:%M')}\n\n"
        f"📥 <b>Harvest Hari Ini:</b>\n"
        f"   ✅ Diindeks baru: {total_indexed} files\n"
        f"   ⏭️ Dilewati (tidak berubah): {total_skipped} files\n"
        f"   ⏱️ Waktu: {elapsed:.0f} detik\n"
    )

    if projects:
        digest_message += f"\n📂 Projects yang diupdate:\n"
        for p in projects[:5]:
            digest_message += f"   • {p}\n"

    digest_message += (
        f"\n📊 <b>Total di Knowledge Base:</b>\n"
        f"   📁 {total_files_in_db:,} file terindeks\n"
        f"   🧩 {total_chunks:,} knowledge chunks\n\n"
        f"<i>Ketik /search &lt;topik&gt; di bot Telegram untuk mencari knowledge</i>"
    )

    await _send_telegram(digest_message)
    logger.info(f"=== Harvest selesai. Diindeks: {total_indexed}, Skipped: {total_skipped} ===")


async def _send_telegram(message: str):
    """Kirim digest ke Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ada di env. Skip digest.")
        return

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            )
            if resp.json().get("ok"):
                logger.info("✅ Daily digest terkirim ke Telegram.")
            else:
                logger.warning(f"Telegram API error: {resp.json()}")
    except Exception as e:
        logger.error(f"Gagal kirim Telegram: {e}")


if __name__ == "__main__":
    asyncio.run(main())
