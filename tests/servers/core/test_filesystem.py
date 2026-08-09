"""Tests for core filesystem tools with path sandboxing."""

from __future__ import annotations

from pathlib import Path

import pytest

from servers.core import filesystem
from shared.security import UnsafePathError


@pytest.fixture()
def fs_dir(allowed_dir: Path) -> Path:
    return allowed_dir


async def test_write_and_read_file(fs_dir: Path) -> None:
    target = str(fs_dir / "test.txt")
    res = await filesystem.write_file(target, "hello world")
    assert "Wrote" in res
    content = await filesystem.read_file(target)
    assert content == "hello world"


async def test_list_directory(fs_dir: Path) -> None:
    (fs_dir / "a.txt").write_text("a", encoding="utf-8")
    (fs_dir / "sub").mkdir()
    items = await filesystem.list_directory(str(fs_dir))
    names = {i["name"] for i in items}
    assert "a.txt" in names
    assert "sub" in names


async def test_search_files(fs_dir: Path) -> None:
    (fs_dir / "one.py").write_text("x", encoding="utf-8")
    (fs_dir / "two.txt").write_text("x", encoding="utf-8")
    results = await filesystem.search_files(str(fs_dir), "*.py")
    assert len(results) == 1
    assert results[0].endswith("one.py")


async def test_delete_file(fs_dir: Path) -> None:
    target = fs_dir / "del.txt"
    target.write_text("x", encoding="utf-8")
    res = await filesystem.delete_file(str(target))
    assert "Deleted" in res
    assert not target.exists()


async def test_move_file(fs_dir: Path) -> None:
    src = fs_dir / "src.txt"
    dst = fs_dir / "dst.txt"
    src.write_text("data", encoding="utf-8")
    res = await filesystem.move_file(str(src), str(dst))
    assert "Moved" in res
    assert dst.exists()
    assert not src.exists()


async def test_read_missing_file_raises(fs_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await filesystem.read_file(str(fs_dir / "nope.txt"))


async def test_filesystem_rejects_traversal(fs_dir: Path) -> None:
    with pytest.raises(UnsafePathError):
        await filesystem.read_file(str(fs_dir) + "/../../etc/hostname")
