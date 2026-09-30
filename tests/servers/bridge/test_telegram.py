"""Tests for the Telegram bridge server (mocked)."""

from __future__ import annotations

from typing import Any

import pytest
from servers.bridge import telegram_server


@pytest.fixture()
def fake_bot(monkeypatch: pytest.MonkeyPatch):
    class FakeMessage:
        def __init__(self, message_id: int, chat_id: str, text: str):
            self.message_id = message_id
            class Chat:
                id = chat_id
            self.chat = Chat()
            self.text = text

    class FakeUpdate:
        def __init__(self, update_id: int, message: FakeMessage):
            self.update_id = update_id
            self.message = message

    class FakeBot:
        def __init__(self, token: str):
            self.token = token

        async def send_message(self, chat_id: str, text: str):
            if chat_id == "error_chat":
                raise ValueError("Chat not found")
            return FakeMessage(42, chat_id, text)

        async def get_updates(self, limit: int = 10):
            if self.token == "error-key":
                raise ValueError("Failed to fetch")
            return [
                FakeUpdate(100, FakeMessage(1, "chat1", "Hello")),
                FakeUpdate(101, FakeMessage(2, "chat2", "World"))
            ][:limit]

    def _get_fake_bot(token: str):
        return FakeBot(token=token)

    monkeypatch.setattr("telegram.Bot", _get_fake_bot)


async def test_telegram_send_message_no_token(reset_settings) -> None:
    from shared import config as config_mod
    config_mod._settings = None
    res = await telegram_server.telegram_send_message("hi", chat_id="test")
    assert res["status"] == "error"
    assert "TELEGRAM_BOT_TOKEN not configured" in res["error"]


async def test_telegram_send_message_no_chat_id(monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    config_mod._settings = None
    res = await telegram_server.telegram_send_message("hi")
    assert res["status"] == "error"
    assert "chat_id not provided" in res["error"]


async def test_telegram_send_message_success(fake_bot, monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    config_mod._settings = None
    # using explicit chat_id
    res = await telegram_server.telegram_send_message("hello", chat_id="chat123")
    assert res["status"] == "sent"
    assert res["message_id"] == 42
    assert res["chat_id"] == "chat123"

    # using fallback chat_id from env
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-env")
    config_mod._settings = None
    res2 = await telegram_server.telegram_send_message("world")
    assert res2["status"] == "sent"
    assert res2["chat_id"] == "chat-env"


async def test_telegram_send_message_bot_error(fake_bot, monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    config_mod._settings = None
    res = await telegram_server.telegram_send_message("hello", chat_id="error_chat")
    assert res["status"] == "error"
    assert "Chat not found" in res["error"]


async def test_telegram_get_updates_success(fake_bot, monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    config_mod._settings = None
    res = await telegram_server.telegram_get_updates(limit=1)
    assert len(res) == 1
    assert res[0]["update_id"] == 100
    assert res[0]["text"] == "Hello"

async def test_telegram_get_updates_error(fake_bot, monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "error-key")
    config_mod._settings = None
    res = await telegram_server.telegram_get_updates(limit=1)
    assert len(res) == 1
    assert res[0]["status"] == "error"
    assert "Failed to fetch" in res[0]["error"]
