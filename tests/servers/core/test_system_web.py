"""Tests for core system info, env access, and web utilities."""

from __future__ import annotations

from typing import Any, Self

import pytest

from servers.core import system, web


async def test_get_system_info() -> None:
    info = await system.get_system_info()
    assert "os" in info
    assert "cpu_cores" in info
    assert "memory_total_gb" in info
    assert "python_version" in info


async def test_get_env_variable_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TEST_VAR", "somevalue")
    res = await system.get_env_variable("MY_TEST_VAR")
    assert res["found"] is True
    assert res["value"] == "somevalue"


async def test_get_env_variable_missing() -> None:
    res = await system.get_env_variable("THIS_VAR_SHOULD_NOT_EXIST_XYZ")
    assert res["found"] is False


async def test_get_env_variable_redacts_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_API_KEY", "secret-abc")
    res = await system.get_env_variable("MY_API_KEY")
    assert res["value"] == "<redacted>"


@pytest.fixture()
def fake_async_client(monkeypatch: pytest.MonkeyPatch):
    """Replace httpx.AsyncClient with a fake returning a canned response."""

    class FakeResponse:
        text = "<html><body>Hello <b>World</b></body></html>"
        status_code = 200

        @property
        def headers(self) -> dict[str, str]:
            return {"content-type": "text/html"}

        @property
        def url(self) -> str:
            return "http://example.com/page"

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str) -> FakeResponse:
            self.called_url = url
            return FakeResponse()

        async def head(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(web.httpx, "AsyncClient", FakeAsyncClient)


async def test_fetch_url_strips_html(fake_async_client) -> None:
    res = await web.fetch_url("http://example.com/page", extract_text=True)
    assert res["status_code"] == 200
    assert "Hello" in res["content"]
    assert "<b>" not in res["content"]


async def test_check_url_status(fake_async_client) -> None:
    res = await web.check_url_status("http://example.com/page")
    assert res["reachable"] is True
    assert res["status_code"] == 200
