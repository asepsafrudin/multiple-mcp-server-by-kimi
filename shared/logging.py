"""Structured logging used by every MCP server."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from shared.config import get_settings


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    log_level = (level or settings.log_level).upper()
    log_path = settings.mcp_root / "logs" / "mcp_unified.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(log_level)
    # Remove existing handlers so we don't duplicate logs across server restarts.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)

    file_handler = logging.FileHandler(str(log_path))
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


class StructuredLogger:
    """Thin wrapper that emits JSON-structured event lines."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        self._logger.log(level, json.dumps({"event": event, **kwargs}, default=str))

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)
