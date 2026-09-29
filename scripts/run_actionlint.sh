#!/usr/bin/env bash
# run_actionlint.sh — Lint GitHub Actions workflows with actionlint.
#
# TASK-153 — CI Self-Validation Gate.
#
# actionlint adds semantic checks that a plain YAML parser cannot do:
#   * deprecated / too-old action refs (e.g. actions/checkout@v3)
#   * `needs:` and matrix references that do not resolve
#   * invalid `${{ }}` expressions
#   * shellcheck on every `run:` block
#
# Resolution order:
#   1. a native `actionlint` binary on PATH (fastest)
#   2. the version-pinned Docker image (identical to what CI runs)
#   3. otherwise: skip loudly — the deterministic checks in
#      scripts/validate_workflows.py have already run
#
# Environment:
#   ACTIONLINT_VERSION   image tag to use                (default: 1.7.7)
#   ACTIONLINT_REQUIRED  "1" = fail instead of skipping  (default: 0)
#
# Usage:
#   bash scripts/run_actionlint.sh
#   ACTIONLINT_REQUIRED=1 bash scripts/run_actionlint.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ACTIONLINT_VERSION="${ACTIONLINT_VERSION:-1.7.7}"
ACTIONLINT_IMAGE="rhysd/actionlint:${ACTIONLINT_VERSION}"
ACTIONLINT_REQUIRED="${ACTIONLINT_REQUIRED:-0}"

if command -v actionlint >/dev/null 2>&1; then
    echo "[actionlint] using native binary: $(command -v actionlint)"
    exec actionlint -color
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "[actionlint] using docker image ${ACTIONLINT_IMAGE}"
    exec docker run --rm \
        -v "${REPO_ROOT}:/repo" \
        -w /repo \
        "${ACTIONLINT_IMAGE}" \
        -color
fi

if [[ "${ACTIONLINT_REQUIRED}" == "1" ]]; then
    cat >&2 <<'EOF'
[actionlint] FAIL: no native actionlint and no usable docker daemon.

Install one of them, then retry:
  - actionlint: https://github.com/rhysd/actionlint#install
  - docker:     https://docs.docker.com/engine/install/
EOF
    exit 1
fi

cat >&2 <<'EOF'
[actionlint] SKIPPED: no native actionlint and no usable docker daemon.
[actionlint] The deterministic checks in scripts/validate_workflows.py already ran,
[actionlint] but semantic checks (action versions, expression validity, shellcheck)
[actionlint] did NOT run. Install actionlint or docker for full coverage, or set
[actionlint] ACTIONLINT_REQUIRED=1 to make this a hard failure.
EOF
exit 0