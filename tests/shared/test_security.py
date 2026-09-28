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


@pytest.mark.parametrize("suffix", ["-evil", "-backup", "x"])
def test_safe_path_rejects_sibling_with_shared_prefix(
    allowed_dir: Path, tmp_path: Path, suffix: str
) -> None:
    """Regression TASK-138: sibling dirs sharing a name prefix must be rejected.

    With allowed ``/tmp/.../test_x0`` the path ``/tmp/.../test_x0-evil/secret.txt``
    used to be accepted because validation compared strings with ``startswith``.
    """
    sibling = tmp_path.parent / f"{tmp_path.name}{suffix}"
    sibling.mkdir(exist_ok=True)
    (sibling / "secret.txt").write_text("SECRET", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        SafePath(str(sibling / "secret.txt"))


def test_safe_path_accepts_allowed_dir_itself(allowed_dir: Path) -> None:
    """The allowed directory itself must remain valid (``==`` case)."""
    assert SafePath(str(allowed_dir)).path == allowed_dir


def test_safe_path_accepts_descendant(allowed_dir: Path) -> None:
    """Descendants of an allowed directory must remain valid."""
    nested = allowed_dir / "nested" / "deeper"
    nested.mkdir(parents=True, exist_ok=True)
    assert SafePath(str(nested)).path == nested


def test_safe_path_rejects_symlink_escape(allowed_dir: Path, tmp_path: Path) -> None:
    """No security regression: a symlink pointing outside stays rejected."""
    outside = tmp_path.parent / "symlink_target_outside"
    outside.mkdir(exist_ok=True)
    (outside / "loot.txt").write_text("loot", encoding="utf-8")
    link = allowed_dir / "escape"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafePathError):
        SafePath(str(link / "loot.txt"))


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
