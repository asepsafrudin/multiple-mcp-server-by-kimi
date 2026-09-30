"""Tests for the Gmail bridge server (mocked)."""

from __future__ import annotations

import pytest
from pathlib import Path

from servers.bridge import gmail_server


@pytest.fixture()
def fake_gmail_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class FakeMessagesResource:
        def list(self, userId, q="", maxResults=10):
            self.q = q
            self.maxResults = maxResults
            class FakeListRequest:
                def execute(self):
                    if q == "error":
                        raise ValueError("List error")
                    return {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
            return FakeListRequest()

        def send(self, userId, body):
            class FakeSendRequest:
                def execute(self):
                    if "error" in body.get("raw", ""):
                        raise ValueError("Send error")
                    return {"id": "sent-msg-123"}
            return FakeSendRequest()

        def get(self, userId, id, format):
            class FakeGetRequest:
                def execute(self):
                    if id == "error":
                        raise ValueError("Get error")
                    return {"id": id, "snippet": "Hello snippet"}
            return FakeGetRequest()

    class FakeUsersResource:
        def messages(self):
            return FakeMessagesResource()

    class FakeService:
        def users(self):
            return FakeUsersResource()

    def fake_build(serviceName, version, credentials):
        return FakeService()

    monkeypatch.setattr("googleapiclient.discovery.build", fake_build)

    class FakeCredentials:
        def __init__(self, *args, **kwargs):
            self.valid = True
            self.expired = False
            self.refresh_token = "fake-refresh"

        @classmethod
        def from_authorized_user_file(cls, filename, scopes):
            return cls()

        def refresh(self, request):
            pass

        def to_json(self):
            return "{}"

    monkeypatch.setattr("google.oauth2.credentials.Credentials", FakeCredentials)
    monkeypatch.setattr("google.auth.transport.requests.Request", lambda: None)


async def test_gmail_list_messages_no_credentials(reset_settings) -> None:
    from shared import config as config_mod
    config_mod._settings = None
    res = await gmail_server.gmail_list_messages()
    assert len(res) == 1
    assert res[0]["status"] == "error"
    assert "Gmail credentials not configured" in res[0]["error"]


async def test_gmail_list_messages_success(fake_gmail_service, monkeypatch: pytest.MonkeyPatch, reset_settings, tmp_path: Path) -> None:
    from shared import config as config_mod
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", "dummy.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_path))
    config_mod._settings = None
    
    res = await gmail_server.gmail_list_messages(max_results=2)
    assert len(res) == 2
    assert res[0]["id"] == "msg1"


async def test_gmail_list_messages_error(fake_gmail_service, monkeypatch: pytest.MonkeyPatch, reset_settings, tmp_path: Path) -> None:
    from shared import config as config_mod
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", "dummy.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_path))
    config_mod._settings = None
    
    res = await gmail_server.gmail_list_messages(query="error")
    assert len(res) == 1
    assert res[0]["status"] == "error"
    assert "List error" in res[0]["error"]


async def test_gmail_send_message_success(fake_gmail_service, monkeypatch: pytest.MonkeyPatch, reset_settings, tmp_path: Path) -> None:
    from shared import config as config_mod
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", "dummy.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_path))
    config_mod._settings = None
    
    res = await gmail_server.gmail_send_message("test@example.com", "Subj", "Body")
    assert res["status"] == "sent"
    assert res["id"] == "sent-msg-123"


async def test_gmail_send_message_error(fake_gmail_service, monkeypatch: pytest.MonkeyPatch, reset_settings, tmp_path: Path) -> None:
    from shared import config as config_mod
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", "dummy.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_path))
    monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
    config_mod._settings = None
    res = await gmail_server.gmail_send_message("test@example.com", "Subj", "error")
    assert res["status"] == "error"


async def test_gmail_get_message_success(fake_gmail_service, monkeypatch: pytest.MonkeyPatch, reset_settings, tmp_path: Path) -> None:
    from shared import config as config_mod
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", "dummy.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_path))
    config_mod._settings = None
    
    res = await gmail_server.gmail_get_message("msg123")
    assert res["status"] == "ok"
    assert res["message"]["id"] == "msg123"
