#!/usr/bin/env python3
"""
start_telegram_bot.py — Jalankan Telegram Knowledge Bot
========================================================
Gunakan ini sebagai daemon atau via cron.

Cara jalankan sebagai daemon:
    nohup python3 /home/aseps/MCP/scripts/start_telegram_bot.py > /home/aseps/MCP/logs/telegram_bot.log 2>&1 &

Cara stop:
    pkill -f start_telegram_bot.py
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, "/home/aseps/MCP")

# Load environment dari config/.env
from pathlib import Path
env_file = Path("/home/aseps/MCP/config/.env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("/home/aseps/MCP/logs/telegram_bot.log"),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    from mcp_unified.intelligence.telegram_intake import run_telegram_bot_polling
    asyncio.run(run_telegram_bot_polling())
