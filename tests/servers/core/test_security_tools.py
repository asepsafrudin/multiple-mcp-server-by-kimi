"""Tests for core security tools (audit_log, hash_string, validate_input, sanitize)."""

from __future__ import annotations

import pytest

from servers.core import security


async def test_hash_string_sha256() -> None:
    h = await security.hash_string("hello")
    assert len(h) == 64
    assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


async def test_hash_string_unsupported_algorithm() -> None:
    with pytest.raises(ValueError):
        await security.hash_string("hello", algorithm="rot13")


async def test_validate_input_tool() -> None:
    res = await security.validate_input("user@example.com", "email")
    assert res["valid"] is True


async def test_sanitize_string_tool() -> None:
    res = await security.sanitize_string("a<b>c")
    assert "<" not in res


async def test_audit_log_writes_entry(
    tmp_path, monkeypatch: pytest.MonkeyPatch, reset_settings
) -> None:
    monkeypatch.setenv("MCP_ROOT", str(tmp_path))
    entry_id = await security.audit_log(
        action="test_delete",
        resource="memory:abc",
        result="success",
        metadata={"namespace": "unit"},
    )
    assert entry_id
    log_path = tmp_path / "logs" / "audit.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "test_delete" in content
