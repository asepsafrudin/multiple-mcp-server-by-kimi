"""FTS5 MATCH sanitisation shared by the memory, knowledge and skills engines.

SQLite FTS5 parses the MATCH operand as a query expression, so raw user input
containing operators or unbalanced punctuation (``C++``, ``(test``, ``search OR``,
``"quote``) raises ``sqlite3.OperationalError`` and breaks the search leg. Every
token is therefore turned into a quoted phrase, which makes FTS5 treat the input
as literal text.

Token-level behaviour (see ``tests/shared/test_fts_safety.py`` for the full
matrix): ``C++`` becomes ``"C++"``, ``search OR`` becomes ``"search" "OR"``, and
an unbalanced quote is doubled inside the phrase instead of ending it.
"""

from __future__ import annotations


def sanitize_fts_match(query: str) -> str:
    """Return an FTS5-safe MATCH expression for arbitrary user *query*.

    Each whitespace-separated token is wrapped in double quotes and internal
    double quotes are doubled. Operators (``OR``/``NEAR``/``+``/``*``/``(``) are
    then literal text instead of query syntax. An empty query yields an empty
    phrase, which is valid syntax and matches nothing instead of raising.
    """
    tokens = [token for token in (query or "").split() if token]
    if not tokens:
        return '""'
    return " ".join('"' + token.replace('"', '""') + '"' for token in tokens)
