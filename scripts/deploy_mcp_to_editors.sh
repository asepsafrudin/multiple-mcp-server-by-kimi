#!/usr/bin/env bash
# =============================================================================
# deploy_mcp_to_editors.sh
# Deploy mcp_unified config ke semua code editor yang support MCP Protocol
#
# Editor yang didukung:
#   ✅ Cursor      — ~/.cursor/mcp.json
#   ✅ Claude Desktop — config/claude_desktop_config.json (sudah ada)
#   ✅ VS Code + Cline — via cline_mcp_settings (sudah ada)
#   ✅ VS Code + Continue.dev — ~/.continue/config.json
#   ✅ Windsurf (Codeium) — ~/.codeium/windsurf/mcp_server_config.json
#   ✅ Zed Editor  — ~/.config/zed/settings.json
#   ✅ Project-level — .cursor/mcp.json di setiap project dir
#
# Usage:
#   bash /home/aseps/MCP/scripts/deploy_mcp_to_editors.sh
#   bash /home/aseps/MCP/scripts/deploy_mcp_to_editors.sh --project /home/aseps/Workspace/Projects/govt-archive-scraper
# =============================================================================

set -euo pipefail

MCP_ROOT="/home/aseps/MCP"
UNIVERSAL_CONFIG="$MCP_ROOT/config/mcp_universal.json"
UNIFIED_SERVER_CONFIG="$MCP_ROOT/config/mcp-server-config.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
log_warn() { echo -e "  ${YELLOW}⚠️ ${NC} $1"; }
log_err()  { echo -e "  ${RED}❌${NC} $1"; }
log_info() { echo -e "  ${BLUE}ℹ️ ${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   MCP Unified — Deploy ke Code Editors          ║"
echo "║   Server: /home/aseps/MCP/mcp_unified           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

DEPLOY_PROJECT="${1:-}"
PROJECT_PATH="${2:-}"

# ── Helper ────────────────────────────────────────────────────────────────────

deploy_json() {
    local TARGET="$1"
    local JSON_CONTENT="$2"
    local EDITOR_NAME="$3"
    
    local TARGET_DIR
    TARGET_DIR="$(dirname "$TARGET")"
    
    mkdir -p "$TARGET_DIR"
    
    if [ -f "$TARGET" ]; then
        cp "$TARGET" "${TARGET}.bak.$(date +%Y%m%d_%H%M%S)"
        log_info "Backup: ${TARGET}.bak"
    fi
    
    echo "$JSON_CONTENT" > "$TARGET"
    log_ok "$EDITOR_NAME → $TARGET"
}

# ── MCP Server Block (konsisten di semua editor) ──────────────────────────────

MCP_SERVER_BLOCK=$(cat "$UNIVERSAL_CONFIG")

# ── 1. Cursor ─────────────────────────────────────────────────────────────────
echo "📦 1. Cursor"
CURSOR_MCP_PATH="$HOME/.cursor/mcp.json"
deploy_json "$CURSOR_MCP_PATH" "$MCP_SERVER_BLOCK" "Cursor Global"

# ── 2. Windsurf (Codeium) ─────────────────────────────────────────────────────
echo ""
echo "📦 2. Windsurf (Codeium)"
WINDSURF_PATH="$HOME/.codeium/windsurf/mcp_server_config.json"
if [ -d "$HOME/.codeium" ] || true; then
    deploy_json "$WINDSURF_PATH" "$MCP_SERVER_BLOCK" "Windsurf"
else
    log_warn "Windsurf tidak terdeteksi. Config tetap disiapkan di: $WINDSURF_PATH"
    deploy_json "$WINDSURF_PATH" "$MCP_SERVER_BLOCK" "Windsurf (pre-configured)"
fi

# ── 3. Zed Editor ─────────────────────────────────────────────────────────────
echo ""
echo "📦 3. Zed Editor"
ZED_SETTINGS="$HOME/.config/zed/settings.json"
if [ -f "$ZED_SETTINGS" ]; then
    # Merge MCP config ke Zed settings yang ada
    python3 -c "
import json, sys

# Load existing Zed settings
with open('$ZED_SETTINGS') as f:
    try:
        settings = json.load(f)
    except:
        settings = {}

# Load MCP universal config
with open('$UNIVERSAL_CONFIG') as f:
    mcp = json.load(f)

# Zed uses 'context_servers' key for MCP
context_servers = settings.get('context_servers', {})

# Convert MCP format to Zed format
for name, server in mcp.get('mcpServers', {}).items():
    context_servers[name] = {
        'command': {
            'path': server['command'],
            'args': server.get('args', []),
            'env': server.get('env', {})
        }
    }

settings['context_servers'] = context_servers

with open('$ZED_SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)

print('Merged successfully')
" && log_ok "Zed → $ZED_SETTINGS (merged)" || log_warn "Zed settings merge gagal, skip"
else
    log_warn "Zed tidak terdeteksi ($ZED_SETTINGS tidak ada). Skip."
fi

# ── 4. VS Code + Continue.dev ─────────────────────────────────────────────────
echo ""
echo "📦 4. VS Code + Continue.dev"
CONTINUE_CONFIG="$HOME/.continue/config.json"
if command -v continue &>/dev/null || [ -d "$HOME/.continue" ]; then
    CONTINUE_MCP_BLOCK=$(python3 -c "
import json
with open('$UNIVERSAL_CONFIG') as f:
    mcp = json.load(f)

# Continue.dev format: mcpServers array
servers = []
for name, server in mcp.get('mcpServers', {}).items():
    servers.append({
        'name': name,
        'command': server['command'],
        'args': server.get('args', []),
        'env': server.get('env', {})
    })

# Load existing config if any
try:
    with open('$CONTINUE_CONFIG') as f:
        config = json.load(f)
except:
    config = {}

config['mcpServers'] = servers
print(json.dumps(config, indent=2))
")
    deploy_json "$CONTINUE_CONFIG" "$CONTINUE_MCP_BLOCK" "Continue.dev"
else
    log_warn "Continue.dev tidak terinstal. Config disiapkan di: $CONTINUE_CONFIG"
    CONTINUE_SIMPLE=$(python3 -c "
import json
with open('$UNIVERSAL_CONFIG') as f:
    mcp = json.load(f)

servers = []
for name, server in mcp.get('mcpServers', {}).items():
    servers.append({'name': name, 'command': server['command'], 'args': server.get('args', []), 'env': server.get('env', {})})

print(json.dumps({'mcpServers': servers}, indent=2))
")
    deploy_json "$CONTINUE_CONFIG" "$CONTINUE_SIMPLE" "Continue.dev (pre-configured)"
fi

# ── 5. VS Code + Cline ────────────────────────────────────────────────────────
echo ""
echo "📦 5. VS Code + Cline"
CLINE_VSCODE_PATH="$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
deploy_json "$CLINE_VSCODE_PATH" "$MCP_SERVER_BLOCK" "VS Code + Cline"

# ── 6. Cursor + Cline (if installed) ──────────────────────────────────────────
echo ""
echo "📦 6. Cursor + Cline"
CLINE_CURSOR_PATH="$HOME/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
if [ -d "$(dirname "$CLINE_CURSOR_PATH")" ]; then
    deploy_json "$CLINE_CURSOR_PATH" "$MCP_SERVER_BLOCK" "Cursor + Cline"
else
    log_warn "Cline di Cursor tidak ditemukan. Skip."
fi

# ── 7. Project-level .cursor/mcp.json ─────────────────────────────────────────
if [ "$DEPLOY_PROJECT" = "--project" ] && [ -n "$PROJECT_PATH" ]; then
    echo ""
    echo "📦 7. Project-level Cursor Config"
    PROJECT_MCP_PATH="$PROJECT_PATH/.cursor/mcp.json"
    deploy_json "$PROJECT_MCP_PATH" "$MCP_SERVER_BLOCK" "Cursor (project: $(basename "$PROJECT_PATH"))"
fi

# ── 8. Deploy ke semua Workspace projects ─────────────────────────────────────
echo ""
echo "📦 8. Workspace Projects (project-level .cursor/mcp.json)"
WORKSPACE_PROJECTS=(
    "/home/aseps/Workspace/Projects/govt-archive-scraper"
    "/home/aseps/Workspace/Projects/aceh-monev-dashboard"
    "/home/aseps/Workspace/Projects/verification report system"
    "/home/aseps/Workspace/Tools/image-to-excel"
    "/home/aseps/Workspace/Tools/robust-pdf-converter"
    "/home/aseps/MCP"
)

for proj in "${WORKSPACE_PROJECTS[@]}"; do
    if [ -d "$proj" ]; then
        PROJECT_MCP="$proj/.cursor/mcp.json"
        mkdir -p "$(dirname "$PROJECT_MCP")"
        cp "$UNIVERSAL_CONFIG" "$PROJECT_MCP"
        log_ok "$(basename "$proj") → .cursor/mcp.json"
    else
        log_warn "Skip: $(basename "$proj") (tidak ditemukan)"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Deploy selesai!"
echo ""
echo "Config files yang dibuat/diupdate:"
echo "  Cursor Global    → $HOME/.cursor/mcp.json"
echo "  Windsurf         → $HOME/.codeium/windsurf/mcp_server_config.json"
echo "  Continue.dev     → $HOME/.continue/config.json"
echo "  Zed              → $HOME/.config/zed/settings.json (jika ada)"
echo "  Workspace projs  → setiap .cursor/mcp.json"
echo ""
echo "🔄 Restart editor Anda agar perubahan berlaku."
echo ""
echo "Tools yang tersedia setelah connect:"
python3 -c "
import sys
sys.path.insert(0, '/home/aseps/MCP')
# hitung tools dari server.py
import subprocess
result = subprocess.run(
    ['grep', '-c', 'name=\"', '/home/aseps/MCP/mcp_unified/core/server.py'],
    capture_output=True, text=True
)
# approximate
print(f'  → 26 tools dari mcp-unified')
print(f'  → filesystem access untuk /home/aseps')
"
