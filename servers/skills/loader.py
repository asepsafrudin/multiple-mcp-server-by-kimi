"""Load skills from on-disk registry files (YAML / JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.logging import get_logger
from shared.models import Skill

logger = get_logger("mcp.skills.loader")


def _maybe_yaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml

        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("yaml_load_failed", path=str(path), error=str(exc))
        return None


def _load_file(path: Path) -> dict[str, Any] | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        if suffix in {".yaml", ".yml"}:
            return _maybe_yaml(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("skill_load_failed", path=str(path), error=str(exc))
    return None


def load_skills_from_disk(registry_dir: Path) -> list[Skill]:
    """Read skill definitions from a directory of YAML/JSON files."""
    skills: list[Skill] = []
    if not registry_dir.exists():
        logger.info("skill_registry_not_found", path=str(registry_dir))
        return skills

    for path in registry_dir.rglob("*"):
        if not path.is_file():
            continue
        data = _load_file(path)
        if not data:
            continue
        if isinstance(data, list):
            for item in data:
                try:
                    skills.append(Skill(**item))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("invalid_skill_entry", path=str(path), error=str(exc))
        elif isinstance(data, dict):
            try:
                skills.append(Skill(**data))
            except Exception as exc:  # noqa: BLE001
                logger.warning("invalid_skill_file", path=str(path), error=str(exc))

    logger.info("skills_loaded_from_disk", count=len(skills), path=str(registry_dir))
    return skills
