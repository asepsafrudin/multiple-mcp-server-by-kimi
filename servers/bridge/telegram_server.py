"""MCP bridge server for Telegram bot integration.

Environment variables required:
  TELEGRAM_BOT_TOKEN - Bot token from @BotFather
  TELEGRAM_CHAT_ID   - Default chat ID for send operations
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

from shared.config import get_settings
from shared.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("mcp.bridge.telegram")

mcp = FastMCP(
    name="mcp-telegram-bridge",
    instructions="Telegram bot bridge. Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
)


def _get_bot():
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured.")
    from telegram import Bot
    return Bot(token=settings.telegram_bot_token)


@mcp.tool()
async def telegram_send_message(text: str, chat_id: str | None = None) -> dict:
    """Send a text message to a Telegram chat."""
    settings = get_settings()
    target = chat_id or settings.telegram_chat_id
    if not target:
        return {"status": "error", "error": "chat_id not provided and TELEGRAM_CHAT_ID not set"}
    try:
        bot = _get_bot()
        message = await bot.send_message(chat_id=target, text=text)
        return {"status": "sent", "message_id": message.message_id, "chat_id": target}
    except Exception as exc:  # noqa: BLE001
        logger.error("telegram_send_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@mcp.tool()
async def telegram_get_updates(limit: int = 10) -> list[dict]:
    """Get recent updates (messages) for the configured bot."""
    try:
        bot = _get_bot()
        updates = await bot.get_updates(limit=limit)
        return [
            {
                "update_id": u.update_id,
                "message_id": u.message.message_id if u.message else None,
                "chat_id": u.message.chat.id if u.message else None,
                "text": u.message.text if u.message else None,
            }
            for u in updates
        ]
    except Exception as exc:  # noqa: BLE001
        logger.error("telegram_updates_failed", error=str(exc))
        return [{"status": "error", "error": str(exc)}]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
