"""Tests for the MikroTik RouterOS bridge server (httpx / asyncssh mocked)."""

from __future__ import annotations

from typing import Any, ClassVar, Self

import pytest

from servers.bridge import mikrotik_server

# ---------------------------------------------------------------------------
# httpx mock
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = b"[]" if payload is None else b"{}"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


class FakeAsyncClient:
    instances: ClassVar[list[FakeAsyncClient]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def request(self, method: str, url: str, params=None, json=None) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "params": params, "json": json})
        return FakeResponse({"board-name": "RouterBoard", "version": "7.13"})


@pytest.fixture()
def fake_client(monkeypatch: pytest.MonkeyPatch):
    FakeAsyncClient.instances.clear()
    monkeypatch.setattr(mikrotik_server.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


# ---------------------------------------------------------------------------
# REST tests
# ---------------------------------------------------------------------------


def _set_creds(monkeypatch: pytest.MonkeyPatch, reset_settings) -> None:
    monkeypatch.setenv("MIKROTIK_HOST", "192.168.88.1")
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.setenv("MIKROTIK_PORT", "443")
    monkeypatch.setenv("MIKROTIK_SCHEME", "https")


async def test_mikrotik_get_identity_no_host(monkeypatch, reset_settings) -> None:
    # Override (not delete) so the real .env cannot leak a value.
    monkeypatch.setenv("MIKROTIK_HOST", "")
    res = await mikrotik_server.mikrotik_get_identity()
    assert res["status"] == "error"
    assert "MIKROTIK_HOST" in res["error"]


async def test_mikrotik_get_identity(
    monkeypatch, reset_settings, fake_client
) -> None:
    _set_creds(monkeypatch, reset_settings)
    res = await mikrotik_server.mikrotik_get_identity()
    assert res["status"] == "ok"
    assert res["data"]["version"] == "7.13"
    assert res["path"] == "system/identity"
    assert (
        fake_client.instances[0].calls[0]["url"]
        == "https://192.168.88.1:443/rest/system/identity"
    )


async def test_mikrotik_get_system_resource(
    monkeypatch, reset_settings, fake_client
) -> None:
    _set_creds(monkeypatch, reset_settings)
    res = await mikrotik_server.mikrotik_get_system_resource()
    assert res["status"] == "ok"
    assert res["data"]["version"] == "7.13"
    assert fake_client.instances[0].calls[0]["url"] == "https://192.168.88.1:443/rest/system/resource"


async def test_mikrotik_run_rest_put(monkeypatch, reset_settings, fake_client) -> None:
    _set_creds(monkeypatch, reset_settings)
    res = await mikrotik_server.mikrotik_run_rest(
        "ip/address", method="PUT", json_body={".id": "*1", "address": "10.0.0.1/24"}
    )
    assert res["status"] == "ok"
    call = fake_client.instances[0].calls[0]
    assert call["method"] == "PUT"
    assert call["url"] == "https://192.168.88.1:443/rest/ip/address"


async def test_mikrotik_ping_payload(monkeypatch, reset_settings, fake_client) -> None:
    _set_creds(monkeypatch, reset_settings)
    await mikrotik_server.mikrotik_ping("8.8.8.8", count=2)
    call = fake_client.instances[0].calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/rest/ping")
    assert call["json"] == {"address": "8.8.8.8", "count": 2}


# ---------------------------------------------------------------------------
# SSH tests
# ---------------------------------------------------------------------------


class FakeSSHResult:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeSSHConn:
    def __init__(self, result: FakeSSHResult) -> None:
        self._result = result

    async def run(self, command: str, check: bool = False, timeout: float = 20.0) -> FakeSSHResult:
        return self._result


class FakeConnectContext:
    def __init__(self, result: FakeSSHResult) -> None:
        self._result = result

    async def __aenter__(self) -> FakeSSHConn:
        return FakeSSHConn(self._result)

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.fixture()
def fake_ssh(monkeypatch: pytest.MonkeyPatch):
    import asyncssh

    connect_args: dict[str, Any] = {}

    def fake_connect(*args: Any, **kwargs: Any) -> FakeConnectContext:
        connect_args.update(args=args, kwargs=kwargs)
        return FakeConnectContext(FakeSSHResult("/system identity\n name=Router1\n"))

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    return connect_args


async def test_mikrotik_ssh_command(
    monkeypatch, reset_settings, fake_ssh
) -> None:
    _set_creds(monkeypatch, reset_settings)
    res = await mikrotik_server.mikrotik_ssh_command("/system identity print")
    assert res["status"] == "ok"
    assert "Router1" in res["stdout"]
    assert fake_ssh["kwargs"]["username"] == "admin"


async def test_mikrotik_export_config(
    monkeypatch, reset_settings, fake_ssh
) -> None:
    _set_creds(monkeypatch, reset_settings)
    res = await mikrotik_server.mikrotik_export_config()
    assert res["status"] == "ok"
    assert res["exit_status"] == 0
    assert "Router1" in res["stdout"]
    assert fake_ssh["args"][0] == "192.168.88.1"  # host passed positionally