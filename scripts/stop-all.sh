#!/usr/bin/env bash
# Stop all MCP background servers started by start-all.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$ROOT/logs/pids"

if [[ ! -d "$PID_DIR" ]]; then
    echo "No PID directory found; nothing to stop."
    exit 0
fi

for pid_file in "$PID_DIR"/*.pid; do
    [[ -f "$pid_file" ]] || continue
    name=$(basename "$pid_file" .pid)
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping mcp-$name (pid $pid)..."
        kill "$pid" || true
    else
        echo "mcp-$name not running."
    fi
    rm -f "$pid_file"
done

echo "All MCP background servers stopped."
