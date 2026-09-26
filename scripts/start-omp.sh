#!/usr/bin/env bash
# Start Oh My Pi (OMP) runtime coding agent session with ACP integration
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export PATH="/home/aseps/.bun/bin:$PATH"

echo "Checking OMP CLI..."
if ! command -v npx &> /dev/null; then
    echo "npm/npx command could not be found. Please install NodeJS."
    exit 1
fi

echo "Starting OMP Agent Terminal with MAF/Hindsight Integration..."
export OMP_CONFIG_DIR="$ROOT/.omp"
export HINDSIGHT_API_LLM_API_KEY="ollama" 

cd "$ROOT"
npx omp acp --config "$OMP_CONFIG_DIR/mcp.json"
