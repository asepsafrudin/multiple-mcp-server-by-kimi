"""Tests for shared security primitives (SafePath, sanitize, validate_input)."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.security import SafePath, UnsafePathError, sanitize_string, validate_input


def test_safe_path_accepts_allowed_file(allowed_dir: Path) -> None:
    p = allowed_dir / "hello.txt"
    p.write_text("hello", encoding="utf-8")
    safe = SafePath(str(p))
    assert safe.path.name == "hello.txt"


def test_safe_path_rejects_traversal(allowed_dir: Path) -> None:
    with pytest.raises(UnsafePathError):
        SafePath(str(allowed_dir) + "/../../etc/passwd")


def test_safe_path_rejects_outside_dir(tmp_path: Path, allowed_dir: Path) -> None:
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    with pytest.raises(UnsafePathError):
        SafePath(str(outside / "x.txt"))


def test_sanitize_string_removes_dangerous_chars() -> None:
    result = sanitize_string('hello <script>"x"</script>')
    assert "<" not in result
    assert ">" not in result
    assert '"' not in result


def test_sanitize_string_truncates() -> None:
    result = sanitize_string("a" * 100, max_length=10)
    assert len(result) == 10


def test_validate_input_email() -> None:
    assert validate_input("user@example.com", "email")["valid"] is True
    assert validate_input("not-an-email", "email")["valid"] is False


def test_validate_input_uuid() -> None:
    assert validate_input("123e4567-e89b-12d3-a456-426614174000", "uuid")["valid"] is True
    assert validate_input("nope", "uuid")["valid"] is False


def test_validate_input_unknown_schema() -> None:
    result = validate_input("x", "unknown")
    assert result["valid"] is False
    assert "Unknown" in result["error"]


def test_validate_input_max_length() -> None:
    result = validate_input("x" * 5000, "alphanumeric", max_length=100)
    assert result["valid"] is False
