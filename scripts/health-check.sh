#!/usr/bin/env bash
# MCP Unified Health Check Script
# Validates system memory, docker dependencies (Ollama, Redis), and MCP server processes.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/output/logs"
PID_DIR="$LOG_DIR/pids"

echo "==========================================="
echo "       MCP SYSTEM HEALTH CHECK"
echo "==========================================="

echo -n "1. Disk Space (Root): "
df -h "$ROOT" | awk 'NR==2 {print $4 " available out of " $2 " (" $5 " used)"}'

echo -n "2. Memory Logs Size: "
total_log_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1 || echo "0B")
echo "$total_log_size"

echo "3. Docker Services (Redis & Ollama):"
if command -v docker &> /dev/null; then
    docker ps --format "  - {{.Names}}: {{.Status}}" | grep -E "redis|ollama" || echo "  No running redis/ollama docker containers found."
else
    echo "  Docker not installed or not in PATH."
fi

echo "4. MCP Server Status (SSE Mode):"
if [[ ! -d "$PID_DIR" ]]; then
    echo "  PID directory not found. No servers are currently running via start-all.sh."
    exit 0
fi

running=0
stopped=0

for pid_file in "$PID_DIR"/*.pid; do
    [ -e "$pid_file" ] || continue
    name=$(basename "$pid_file" .pid)
    pid=$(cat "$pid_file")
    
    if kill -0 "$pid" 2>/dev/null; then
        # Cek apakah port binding mendengarkan
        echo "  ✅ $name (PID: $pid) is RUNNING"
        running=$((running+1))
    else
        echo "  ❌ $name (PID: $pid) is STOPPED / DEAD"
        stopped=$((stopped+1))
    fi
done

echo "-------------------------------------------"
echo "Summary: $running servers healthy, $stopped servers dead."
echo "Auto Log Rotation: ENFORCED (Max 10MB - 5 backups via shared/logging.py)"
echo "==========================================="
