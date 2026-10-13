"""TASK-139 regression: harvester melewati berkas kredensial + knowledge_index menolak root di luar allowed."""

from __future__ import annotations

import asyncio
from pathlib import Path

from servers.knowledge import harvester
from servers.knowledge.server import knowledge_index


def test_credential_files_are_skipped():
    for name in (
        "credentials.json",
        "my_secret.txt",
        "api_token.md",
        "service-account-key.json",
        "id_rsa.pem",
        "app.key",
    ):
        assert harvester._should_skip(Path("/tmp/proj") / name) is True, name


def test_credentials_directory_is_skipped():
    assert harvester._should_skip(Path("/tmp/config/credentials/gcp.json")) is True


def test_normal_source_file_is_not_skipped():
    assert harvester._should_skip(Path("/tmp/proj/src/app.py")) is False


def test_knowledge_index_rejects_root_outside_allowed():
    res = asyncio.run(knowledge_index(project="demo", root="/etc"))
    assert res.get("status") == "error"
    assert "not allowed" in res.get("error", "").lower()
