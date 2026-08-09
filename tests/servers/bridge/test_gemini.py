"""Tests for the Gemini bridge server (httpx mocked)."""

from __future__ import annotations

from typing import Any, Self

import pytest

from servers.bridge import gemini_server


@pytest.fixture()
def fake_client(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
            self.called_url = url
            self.called_payload = json
            return FakeResponse(
                {"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}
            )

    monkeypatch.setattr(gemini_server.httpx, "AsyncClient", FakeAsyncClient)


async def test_gemini_generate_no_key() -> None:
    res = await gemini_server.gemini_generate("hi")
    assert res["status"] == "error"
    assert "not configured" in res["error"]


async def test_gemini_generate_success(
    fake_client, monkeypatch: pytest.MonkeyPatch, reset_settings
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    res = await gemini_server.gemini_generate("hello", model="gemini-1.5-flash-latest")
    assert res["status"] == "ok"
    assert res["text"] == "Hello from Gemini"
    assert res["model"] == "gemini-1.5-flash-latest"
