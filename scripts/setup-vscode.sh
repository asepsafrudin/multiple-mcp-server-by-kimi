#!/usr/bin/env bash

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Mengonfigurasi MCP untuk VS Code Extensions (Cline / Roo Code)..."

# 1. Workspace Local (Roo Code / Cline modern mendukung ini)
mkdir -p "$ROOT/.vscode"
cp "$ROOT/config/mcp_universal.json" "$ROOT/.vscode/cline_mcp_settings.json"
echo "[OK] Workspace lokal (.vscode/cline_mcp_settings.json) berhasil dibuat."

# 2. Global Storage VS Code Linux/WSL (Untuk Cline lama)
CLINE_GLOBAL="$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings"
if [ -d "$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev" ]; then
    mkdir -p "$CLINE_GLOBAL"
    cp "$ROOT/config/mcp_universal.json" "$CLINE_GLOBAL/cline_mcp_settings.json"
    echo "[OK] Konfigurasi Global Cline (VS Code) berhasil disinkronkan."
fi

# 3. Global Storage Roo Code (VS Code)
ROO_GLOBAL="$HOME/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings"
if [ -d "$HOME/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline" ]; then
    mkdir -p "$ROO_GLOBAL"
    cp "$ROOT/config/mcp_universal.json" "$ROO_GLOBAL/cline_mcp_settings.json"
    echo "[OK] Konfigurasi Global Roo Code (VS Code) berhasil disinkronkan."
fi

echo "Konfigurasi VS Code selesai! Silakan reload jendela (Developer: Reload Window) di VS Code Anda."
