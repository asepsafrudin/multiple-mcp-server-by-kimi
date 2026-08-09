"""Tests for core shell execution with command whitelisting."""

from __future__ import annotations

from pathlib import Path

import pytest

from servers.core import shell
from shared.security import UnsafePathError


async def test_run_echo(allowed_dir: Path) -> None:
    res = await shell.run_shell("echo hello", cwd=str(allowed_dir))
    assert res["success"] is True
    assert "hello" in res["stdout"]


def test_reject_metacharacters() -> None:
    with pytest.raises(ValueError):
        shell._validate_command("echo hi; rm -rf /")


def test_reject_pipeline() -> None:
    with pytest.raises(ValueError):
        shell._validate_command("ls | grep x")


def test_reject_unlisted_command() -> None:
    with pytest.raises(ValueError):
        shell._validate_command("some_unknown_tool --flag")


async def test_reject_disallowed_cwd(allowed_dir: Path) -> None:
    outside = allowed_dir.parent / "outside_cwd"
    outside.mkdir(exist_ok=True)
    with pytest.raises(UnsafePathError):
        await shell.run_shell("pwd", cwd=str(outside))


def test_empty_command_rejected() -> None:
    with pytest.raises(ValueError):
        shell._validate_command("   ")
