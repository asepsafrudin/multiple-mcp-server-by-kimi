"""Tests for scripts/validate_workflows.py (TASK-153 CI self-validation gate).

The most important test in this module is
``test_repository_workflows_are_valid``: it runs the validator against the
repository's real ``.github/workflows`` directory, so a broken workflow is
caught by ``make test`` and not only by CI.

``test_colon_in_plain_scalar_is_rejected`` locks in the exact regression that
TASK-153 exists to prevent: a ``": "`` inside a plain YAML scalar makes the
whole workflow unparseable.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_workflows.py"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def _load_module() -> object:
    """Load scripts/validate_workflows.py without requiring it to be a package."""
    spec = importlib.util.spec_from_file_location("validate_workflows_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vw = _load_module()


def _write(tmp_path: Path, text: str, name: str = "workflow.yml") -> Path:
    """Write a workflow file from a dedented triple-quoted string."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


VALID = """\
    name: Demo
    on:
      push:
        branches: [main]
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout
            uses: actions/checkout@v4
          - name: Greet
            run: echo hello
    """


def test_valid_workflow_passes(tmp_path: Path) -> None:
    """A minimal well-formed workflow produces no errors."""
    assert vw.validate_file(_write(tmp_path, VALID)) == []


def test_yaml12_on_key_is_a_string(tmp_path: Path) -> None:
    """`on:` must parse as the string "on", not boolean True (YAML 1.1 gotcha)."""
    import yaml

    doc = yaml.load(
        textwrap.dedent(VALID).lstrip(),
        Loader=vw._StrictLoader,
    )
    assert "on" in doc, f"expected string key 'on', got keys {list(doc)}"
    assert True not in doc, "PyYAML YAML 1.1 boolean coercion leaked into the parser"


def test_colon_in_plain_scalar_is_rejected(tmp_path: Path) -> None:
    """Regression guard: `\"...advisory: non-blocking\"` in a plain scalar is invalid YAML."""
    broken = """\
        name: CI
        on:
          push:
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - name: advisory
                run: mypy shared servers || echo "advisory: non-blocking"
        """
    errors = vw.validate_file(_write(tmp_path, broken))
    assert errors, "expected the validator to reject a colon inside a plain scalar"
    assert "YAML error" in errors[0]
    assert "line" in errors[0], f"error should carry a line number, got: {errors[0]}"


def test_missing_runs_on_is_rejected(tmp_path: Path) -> None:
    """A job that neither runs on a runner nor calls a reusable workflow is invalid."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          build:
            steps:
              - run: echo hi
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("missing 'runs-on'" in e for e in errors), errors


def test_reusable_workflow_job_allows_uses_without_runs_on(tmp_path: Path) -> None:
    """A `uses:`-only job is a reusable workflow call and needs no `runs-on`."""
    good = """\
        name: CI
        on:
          push:
        jobs:
          call:
            uses: owner/repo/.github/workflows/reusable.yml@v1
            with:
              arg: value
        """
    assert vw.validate_file(_write(tmp_path, good)) == []


def test_runs_on_together_with_uses_is_rejected(tmp_path: Path) -> None:
    """GitHub rejects `runs-on` on a reusable-workflow-call job."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          call:
            runs-on: ubuntu-latest
            uses: owner/repo/.github/workflows/reusable.yml@v1
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("'runs-on' is not allowed together with 'uses'" in e for e in errors), errors


@pytest.mark.parametrize(
    ("label", "step_yaml", "expected"),
    [
        ("neither", "              - name: nothing", "has neither 'uses' nor 'run'"),
        (
            "both",
            "              - name: both\n                uses: actions/checkout@v4\n                run: echo hi",
            "has both 'uses' and 'run'",
        ),
    ],
)
def test_step_must_have_exactly_one_of_uses_or_run(
    tmp_path: Path, label: str, step_yaml: str, expected: str
) -> None:
    """Each step needs exactly one of `uses` / `run`."""
    bad = (
        "name: CI\non:\n  push:\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n{step_yaml}\n"
    )
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any(expected in e for e in errors), f"{label}: {errors}"


def test_unknown_needs_reference_is_rejected(tmp_path: Path) -> None:
    """`needs:` must point at a job that exists."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            needs: nonexistent
            steps:
              - run: echo hi
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("references unknown job 'nonexistent'" in e for e in errors), errors


def test_self_referencing_needs_is_rejected(tmp_path: Path) -> None:
    """A job cannot depend on itself."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            needs: build
            steps:
              - run: echo hi
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("cannot depend on itself" in e for e in errors), errors


def test_needs_cycle_is_rejected(tmp_path: Path) -> None:
    """A cycle in the `needs` graph is detected."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          a:
            runs-on: ubuntu-latest
            needs: b
            steps:
              - run: echo a
          b:
            runs-on: ubuntu-latest
            needs: a
            steps:
              - run: echo b
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("dependency cycle detected" in e for e in errors), errors


def test_duplicate_key_is_rejected(tmp_path: Path) -> None:
    """A repeated job key is silently collapsed by PyYAML unless we check for it."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo first
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo second
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("duplicate key" in e for e in errors), errors


def test_duplicate_key_check_can_be_disabled(tmp_path: Path) -> None:
    """With the check off, the file is accepted (last key wins)."""
    duplicate = """\
        name: CI
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo first
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo second
        """
    path = _write(tmp_path, duplicate)
    assert vw.validate_file(path, check_duplicate_keys=False) == []


def test_missing_on_trigger_is_rejected(tmp_path: Path) -> None:
    """A workflow with no triggers is an error."""
    bad = """\
        name: CI
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("missing top-level 'on' trigger" in e for e in errors), errors


def test_missing_jobs_is_rejected(tmp_path: Path) -> None:
    """A workflow with no jobs is an error."""
    bad = "name: CI\non:\n  push:\n"
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("missing top-level 'jobs' mapping" in e for e in errors), errors


def test_non_mapping_top_level_is_rejected(tmp_path: Path) -> None:
    """Top level must be a mapping."""
    errors = vw.validate_file(_write(tmp_path, "- just\n- a\n- list\n"))
    assert any("top level must be a mapping" in e for e in errors), errors


def test_empty_steps_list_is_rejected(tmp_path: Path) -> None:
    """`steps` must be a non-empty list."""
    bad = """\
        name: CI
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps: []
        """
    errors = vw.validate_file(_write(tmp_path, bad))
    assert any("must be a non-empty list" in e for e in errors), errors


def test_missing_file_reports_error(tmp_path: Path) -> None:
    """A path that does not exist is reported, not raised."""
    errors = vw.validate_file(tmp_path / "absent.yml")
    assert errors and "cannot read file" in errors[0]


class TestCollectTargets:
    """Tests for directory expansion and de-duplication."""

    def test_directory_expansion_and_sorting(self, tmp_path: Path) -> None:
        for name in ("b.yml", "a.yaml", "notes.txt"):
            (tmp_path / name).write_text(
                "name: x\non:\n  push:\njobs:\n  j:\n    runs-on: x\n    steps:\n      - run: y\n"
            )
        targets = [p.name for p in vw.collect_targets([str(tmp_path)])]
        assert targets == ["a.yaml", "b.yml"], "only *.yml/*.yaml, sorted, no duplicates"


class TestCli:
    """End-to-end CLI behaviour."""

    def test_cli_returns_zero_for_valid_directory(self, tmp_path: Path) -> None:
        valid = textwrap.dedent(VALID).lstrip().replace("workflow", "workflow")
        (tmp_path / "wf.yml").write_text(valid, encoding="utf-8")
        assert vw.main([str(tmp_path), "--quiet"]) == 0

    def test_cli_returns_one_for_invalid_directory(self, tmp_path: Path) -> None:
        (tmp_path / "wf.yml").write_text("name: x\non:\n  push:\n", encoding="utf-8")
        assert vw.main([str(tmp_path), "--quiet"]) == 1

    def test_cli_returns_one_when_nothing_found(self, tmp_path: Path) -> None:
        assert vw.main([str(tmp_path), "--quiet"]) == 1


@pytest.mark.skipif(not WORKFLOWS_DIR.is_dir(), reason="no .github/workflows directory")
def test_repository_workflows_are_valid() -> None:
    """Self-check: the repository's own workflows must pass the gate."""
    assert vw.main([str(WORKFLOWS_DIR)]) == 0, "a workflow in this repository is invalid"


@pytest.mark.skipif(not WORKFLOWS_DIR.is_dir(), reason="no .github/workflows directory")
def test_every_repository_workflow_has_at_least_one_job() -> None:
    """Guard against a workflow file that parses but does nothing."""
    import yaml

    for path in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=vw._StrictLoader)
        assert doc.get("jobs"), f"{path.name} has no jobs"
        assert "on" in doc, f"{path.name} has no trigger"
