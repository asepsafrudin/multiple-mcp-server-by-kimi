#!/usr/bin/env bash
# test_with_postgres.sh — Jalankan test suite repo dengan PostgreSQL sekali-pakai (pgvector).
# Membuat container sementara, menyediakan DB_URL, menjalankan pytest, lalu membersihkan.
#
# Usage: bash scripts/test_with_postgres.sh [args pytest tambahan...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PG_TEST_PORT:-55432}"
NAME="${PG_TEST_NAME:-mcp-test-pg}"
IMAGE="${PG_TEST_IMAGE:-pgvector/pgvector:pg15}"
PYTHON="${PYTHON:-python}"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
echo "[test-pg] start $IMAGE di :$PORT ..."
docker run -d --name "$NAME" \
  -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=mcp_test \
  -p "$PORT:5432" "$IMAGE" >/dev/null

for _ in $(seq 1 30); do
  pg_isready -h localhost -p "$PORT" >/dev/null 2>&1 && break
  sleep 1
done
pg_isready -h localhost -p "$PORT" >/dev/null 2>&1 || { echo "[test-pg] PostgreSQL tidak siap"; exit 1; }

export DB_URL="postgresql://test:test@localhost:$PORT/mcp_test"
echo "[test-pg] DB_URL=$DB_URL ; menjalankan pytest ..."
cd "$ROOT"
"$PYTHON" -m pytest tests "$@"
