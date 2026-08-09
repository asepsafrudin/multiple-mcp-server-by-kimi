#!/usr/bin/env bash
# Start all MCP servers in the background using SSE transport.
# For editor/IDE integration, use the stdio configs in config/ instead.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
LOG_DIR="$ROOT/logs"
PID_DIR="$LOG_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found at $VENV"
    echo "Run: make install"
    exit 1
fi

PYTHON="$VENV/bin/python"
export MCP_ROOT="$ROOT"

SERVERS=(
    "core:servers.core.server:8000"
    "memory:servers.memory.server:8001"
    "knowledge:servers.knowledge.server:8002"
    "skills:servers.skills.server:8003"
    "gmail:servers.bridge.gmail_server:8004"
    "telegram:servers.bridge.telegram_server:8005"
    "gemini:servers.bridge.gemini_server:8006"
    "vision:servers.bridge.vision_server:8007"
)

for entry in "${SERVERS[@]}"; do
    IFS=':' read -r name module port <<< "$entry"
    pid_file="$PID_DIR/$name.pid"
    log_file="$LOG_DIR/mcp-$name.log"

    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "mcp-$name already running (pid $(cat "$pid_file"))"
        continue
    fi

    echo "Starting mcp-$name on port $port..."
    nohup "$PYTHON" -m "$module" --transport sse --port "$port" --host 127.0.0.1 > "$log_file" 2>&1 &
    echo $! > "$pid_file"
done

echo "All MCP servers started. Logs: $LOG_DIR"
echo "Endpoints:"
for entry in "${SERVERS[@]}"; do
    IFS=':' read -r name _ port <<< "$entry"
    echo "  http://127.0.0.1:$port/sse  -> mcp-$name"
done
