#!/usr/bin/env python3
"""Validate GitHub Actions workflow files deterministically.

TASK-153 — CI Self-Validation Gate.

Why this exists
---------------
Sprint 1 shipped four workflows that were never executed. One of them contained
a plain YAML scalar with `": "` inside it, which makes the whole document
unparseable — GitHub Actions would have rejected the file outright. Nothing in
the pipeline would have caught that before merge.

This script is the always-available half of the gate (no external tools, only
PyYAML). It catches the classes of mistake that are deterministically checkable:

  * YAML syntax errors, including the `": "`-in-plain-scalar footgun
  * duplicate keys (PyYAML silently keeps the last one by default)
  * a missing top-level `jobs` mapping, or a missing `on` trigger
  * a job without an execution strategy (`runs-on` + `steps`, or `uses`)
  * a job whose `steps` are not a non-empty list
  * a step with neither `uses` nor `run`, or with both
  * `needs:` pointing at a job that does not exist, or at itself
  * cyclic `needs` chains

Semantic checks that need GitHub's own schema (expression evaluation, action
inputs, matrix expansion) are delegated to `actionlint`, which is wired up in
`scripts/run_actionlint.sh`, the `ci-lint` Make target and the CI
`workflow-lint` job.

Usage
-----
    python3 scripts/validate_workflows.py
    python3 scripts/validate_workflows.py .github/workflows/ci.yml
    python3 scripts/validate_workflows.py --quiet

Exit status is 0 when every file is valid, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    print(
        "FAIL: PyYAML is required to validate workflow files.\n"
        "      Install it with: pip install pyyaml",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

DEFAULT_TARGET = ".github/workflows"
WORKFLOW_SUFFIXES = {".yml", ".yaml"}


class _WorkflowLoader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans, matching GitHub Actions.

    PyYAML implements YAML 1.1, where ``on``, ``off``, ``yes`` and ``no`` are
    booleans. That silently turns the workflow trigger key ``on:`` into the key
    ``True``, which breaks any consumer expecting the string ``\"on\"``.
    GitHub Actions uses YAML 1.2, so only ``true``/``false`` are booleans here.
    """


def _install_yaml12_bool_resolver(loader: type[yaml.SafeLoader]) -> None:
    """Restrict boolean resolution to ``true``/``false`` on ``loader``."""
    bool_tag = "tag:yaml.org,2002:bool"
    # Build a fresh dict so yaml.SafeLoader's own resolvers are left untouched.
    loader.yaml_implicit_resolvers = {
        first: [entry for entry in entries if entry[0] != bool_tag]
        for first, entries in loader.yaml_implicit_resolvers.items()
    }
    loader.add_implicit_resolver(
        bool_tag,
        re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
        list("tTfF"),
    )


class _StrictLoader(_WorkflowLoader):
    """Workflow loader that additionally refuses duplicate mapping keys.

    Plain ``yaml.safe_load`` silently keeps the last value for a repeated key.
    For workflows that is dangerous: a duplicated step or job key disappears
    without any warning.
    """


def _construct_mapping(
    loader: _WorkflowLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    """Build a mapping, raising on duplicate keys."""
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError:  # unhashable key
            duplicate = False
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_install_yaml12_bool_resolver(_WorkflowLoader)
_install_yaml12_bool_resolver(_StrictLoader)
_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _format_mark(mark: yaml.Mark | None) -> str:
    """Render a YAML mark as ``line/column`` for error messages."""
    if mark is None:
        return ""
    return f" (line {mark.line + 1}, column {mark.column + 1})"


def _as_list(value: Any) -> list[Any]:
    """Normalise a scalar-or-list YAML value into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _check_job(job_id: str, job: Any, errors: list[str]) -> tuple[list[str], list[str]]:
    """Validate a single job entry.

    Returns:
        A tuple of (needs, step_descriptions) accumulated for this job.
    """
    if not isinstance(job, dict):
        errors.append(f"jobs.{job_id}: must be a mapping, got {type(job).__name__}")
        return [], []

    needs = [str(n) for n in _as_list(job.get("needs"))]

    # A job either calls a reusable workflow (`uses`) or runs steps on a runner.
    if "uses" in job:
        if "runs-on" in job:
            errors.append(
                f"jobs.{job_id}: 'runs-on' is not allowed together with 'uses' "
                "(reusable workflow calls do not run on a runner)"
            )
        return needs, []

    if "runs-on" not in job:
        errors.append(f"jobs.{job_id}: missing 'runs-on' (or 'uses' for a reusable workflow call)")

    steps = job.get("steps")
    if steps is None:
        errors.append(f"jobs.{job_id}: missing 'steps'")
        return needs, []

    if not isinstance(steps, list) or not steps:
        errors.append(f"jobs.{job_id}.steps: must be a non-empty list, got {type(steps).__name__}")
        return needs, []

    described: list[str] = []
    for index, step in enumerate(steps):
        where = f"jobs.{job_id}.steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{where}: must be a mapping, got {type(step).__name__}")
            continue
        has_uses = "uses" in step
        has_run = "run" in step
        described.append(str(step.get("name") or step.get("uses") or where))
        if has_uses and has_run:
            errors.append(f"{where}: has both 'uses' and 'run'; exactly one is allowed")
        elif not has_uses and not has_run:
            errors.append(f"{where}: has neither 'uses' nor 'run'")

    return needs, described


def _find_cycles(graph: dict[str, list[str]]) -> list[str]:
    """Return a list of human-readable cycle descriptions (empty when acyclic)."""
    cycles: list[str] = []
    state: dict[str, int] = {}  # 0 = unvisited, 1 = on stack, 2 = done
    stack: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for neighbour in graph.get(node, []):
            if neighbour not in graph:
                continue
            if state.get(neighbour, 0) == 1:
                start = stack.index(neighbour)
                cycles.append(" -> ".join([*stack[start:], neighbour]))
            elif state.get(neighbour, 0) == 0:
                visit(neighbour)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


def validate_document(doc: Any, label: str) -> list[str]:
    """Validate a parsed workflow document. Returns a list of error strings."""
    errors: list[str] = []

    if not isinstance(doc, dict):
        return [f"{label}: top level must be a mapping, got {type(doc).__name__}"]

    if not any(str(key) == "on" for key in doc):
        errors.append(f"{label}: missing top-level 'on' trigger")

    jobs = doc.get("jobs")
    if jobs is None:
        errors.append(f"{label}: missing top-level 'jobs' mapping")
        return errors
    if not isinstance(jobs, dict) or not jobs:
        errors.append(f"{label}: 'jobs' must be a non-empty mapping, got {type(jobs).__name__}")
        return errors

    graph: dict[str, list[str]] = {}
    for job_id, job in jobs.items():
        job_id = str(job_id)
        needs, _ = _check_job(job_id, job, errors)
        graph[job_id] = needs

    for job_id, needs in graph.items():
        for dependency in needs:
            if dependency == job_id:
                errors.append(f"jobs.{job_id}.needs: cannot depend on itself")
            elif dependency not in graph:
                errors.append(
                    f"jobs.{job_id}.needs: references unknown job {dependency!r}; "
                    f"known jobs are {sorted(graph)}"
                )

    for cycle in _find_cycles(graph):
        errors.append(f"jobs.needs: dependency cycle detected: {cycle}")

    return errors


def validate_file(path: Path, *, check_duplicate_keys: bool = True) -> list[str]:
    """Validate one workflow file. Returns a list of error strings."""
    label = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{label}: cannot read file: {exc}"]

    if check_duplicate_keys:
        loader: type[yaml.SafeLoader] = _StrictLoader
    else:
        loader = _WorkflowLoader

    try:
        doc = yaml.load(text, Loader=loader)
    except yaml.MarkedYAMLError as exc:
        return [f"{label}: YAML error: {exc.problem or exc}{_format_mark(exc.problem_mark)}"]
    except yaml.YAMLError as exc:
        return [f"{label}: YAML error: {exc}"]

    return validate_document(doc, label)


def collect_targets(raw_paths: list[str]) -> list[Path]:
    """Expand CLI arguments into a sorted list of workflow files."""
    found: list[Path] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(
                child
                for child in path.iterdir()
                if child.is_file() and child.suffix in WORKFLOW_SUFFIXES
            )
        else:
            found.append(path)
    # De-duplicate while keeping a deterministic order.
    return sorted({p for p in found})


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Validate GitHub Actions workflow files.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[DEFAULT_TARGET],
        help=f"files or directories to validate (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print failures",
    )
    parser.add_argument(
        "--no-duplicate-key-check",
        action="store_true",
        help="use plain yaml.SafeLoader (duplicate keys are silently merged)",
    )
    args = parser.parse_args(argv)

    targets = collect_targets(args.paths)
    if not targets:
        print(f"FAIL: no workflow files found in {args.paths}", file=sys.stderr)
        return 1

    failures = 0
    for path in targets:
        if not path.exists():
            print(f"FAIL {path}: file does not exist")
            failures += 1
            continue
        errors = validate_file(path, check_duplicate_keys=not args.no_duplicate_key_check)
        if errors:
            failures += 1
            for message in errors:
                print(f"FAIL {message}")
        elif not args.quiet:
            print(f"OK   {path}")

    if failures:
        print(f"\n{failures} of {len(targets)} workflow file(s) failed validation")
        return 1

    if not args.quiet:
        print(f"\nAll {len(targets)} workflow file(s) are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())