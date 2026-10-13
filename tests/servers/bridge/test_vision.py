"""Tests for the Vision OCR bridge server (TASK-139: path guard)."""

from __future__ import annotations

import pytest
import httpx

from servers.bridge import vision_server


@pytest.fixture()
def fake_vision_client(monkeypatch: pytest.MonkeyPatch):
    class FakeCredentials:
        def __init__(self, *args, **kwargs):
            self.token = "fake-token"

        @classmethod
        def from_service_account_file(cls, filename, scopes):
            return cls()

        def refresh(self, request):
            pass

    monkeypatch.setattr("google.oauth2.service_account.Credentials", FakeCredentials)
    monkeypatch.setattr("google.auth.transport.requests.Request", lambda: None)

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code != 200:
                raise ValueError("HTTP Error")

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

        async def post(self, url, json, headers=None):
            if "vision.googleapis.com" in url:
                if "error" in json["requests"][0]["image"]["content"]:
                    raise ValueError("Simulated Vision API Error")
                return FakeResponse({
                    "responses": [{"textAnnotations": [{"description": "Hello World Vision"}]}]
                })
            # Ollama fallback: paksa ganti model (404) lalu sukses.
            if json["model"] == "llama3.2-vision":
                return FakeResponse({}, 404)
            return FakeResponse({"response": "Fallback Text"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)


async def test_vision_ocr_rejects_outside_allowed(allowed_dir) -> None:
    res = await vision_server.vision_ocr("/etc/passwd")
    assert res["status"] == "error"
    assert "not allowed" in res["error"].lower()


async def test_vision_ocr_no_credentials(allowed_dir) -> None:
    from shared import config as config_mod
    config_mod._settings = None
    img_path = allowed_dir / "test.png"
    img_path.write_bytes(b"dummy")
    res = await vision_server.vision_ocr(str(img_path))
    assert res["status"] == "error"
    assert "GOOGLE_VISION_CREDENTIALS_PATH not configured" in res["error"]


async def test_vision_ocr_not_found(allowed_dir) -> None:
    res = await vision_server.vision_ocr(str(allowed_dir / "missing.png"))
    assert res["status"] == "error"
    assert "File not found" in res["error"]


async def test_vision_ocr_success(fake_vision_client, monkeypatch: pytest.MonkeyPatch, allowed_dir) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("GOOGLE_VISION_CREDENTIALS_PATH", "dummy.json")
    config_mod._settings = None
    img_path = allowed_dir / "test.png"
    img_path.write_bytes(b"dummy image")

    res = await vision_server.vision_ocr(str(img_path))
    assert res["status"] == "ok"
    assert res["text"] == "Hello World Vision"
    assert res["source"] == "google_cloud_vision"


async def test_vision_ocr_fallback_success(fake_vision_client, monkeypatch: pytest.MonkeyPatch, allowed_dir) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("GOOGLE_VISION_CREDENTIALS_PATH", "dummy.json")
    config_mod._settings = None
    img_path = allowed_dir / "test.png"
    img_path.write_bytes(b"~error~")
    # "error" pada base64 -> memicu kegagalan Google Vision -> fallback Ollama.
    monkeypatch.setattr(vision_server.base64, "b64encode", lambda x: b"error_trigger")

    res = await vision_server.vision_ocr(str(img_path))
    assert res["status"] == "ok"
    assert res["text"] == "Fallback Text"
    assert "ollama" in res["source"]


async def test_vision_ocr_fallback_error(fake_vision_client, monkeypatch: pytest.MonkeyPatch, allowed_dir) -> None:
    from shared import config as config_mod
    monkeypatch.setenv("GOOGLE_VISION_CREDENTIALS_PATH", "dummy.json")
    config_mod._settings = None
    img_path = allowed_dir / "test.png"
    img_path.write_bytes(b"~error~")
    monkeypatch.setattr(vision_server.base64, "b64encode", lambda x: b"error_trigger_full")

    class FakeThrowingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

        async def post(self, url, json, headers=None):
            raise ValueError("All API Fail")

    monkeypatch.setattr(httpx, "AsyncClient", FakeThrowingClient)

    res = await vision_server.vision_ocr(str(img_path))
    assert res["status"] == "error"
    assert "All API Fail" in res["error"]
