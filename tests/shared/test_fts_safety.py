"""Tests for FTS5 MATCH sanitiser (TASK-140)."""

from __future__ import annotations

import sqlite3

import pytest

from shared.fts_safety import sanitize_fts_match


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("C++", '"C++"'),
        ("(test", '"(test"'),
        ("search OR", '"search" "OR"'),
        ('unbalanced "quote', '"unbalanced" """quote"'),
        ("", '""'),
        ("   ", '""'),
        ("hello world", '"hello" "world"'),
    ],
)
def test_sanitize_fts_match_quotes_tokens(raw: str, expected: str) -> None:
    assert sanitize_fts_match(raw) == expected


@pytest.mark.parametrize("raw", ["C++", "(test", "search OR", 'unbalanced "quote', "", "   "])
def test_sanitized_queries_are_accepted_by_fts5(raw: str) -> None:
    """Raw input used to raise OperationalError; sanitised input must not."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(c, tokenize='trigram')")
    con.execute("INSERT INTO t VALUES ('C++ operator overload (test) search OR quote')")
    # Must not raise.
    con.execute("SELECT count(*) FROM t WHERE t MATCH ?", (sanitize_fts_match(raw),)).fetchone()
    con.close()


def test_raw_query_still_crashes_without_sanitiser() -> None:
    """Documents the original defect: the raw query is rejected by FTS5."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(c, tokenize='trigram')")
    with pytest.raises(sqlite3.OperationalError):
        con.execute("SELECT count(*) FROM t WHERE t MATCH ?", ("C++",)).fetchone()
    con.close()
