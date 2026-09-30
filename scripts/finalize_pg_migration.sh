#!/usr/bin/env bash
# MCP Database Migration Finalization Script
# Script eksekutor satu klik untuk menyelesaikan migrasi Postgres 100%.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==========================================="
echo "   MCP POSTGRESQL MIGRATION FINALIZER"
echo "==========================================="
echo ""
echo "1. Menyambungkan rute (Hot-swap) endpoint..."
sed -i 's/from servers.memory import engine/from servers.memory import pg_engine as engine/g' "$ROOT/servers/memory/server.py"
sed -i 's/from servers.memory import hindsight_engine/from servers.memory import pg_hindsight_engine as hindsight_engine/g' "$ROOT/servers/memory/server.py"

sed -i 's/from servers.knowledge import engine/from servers.knowledge import pg_engine as engine/g' "$ROOT/servers/knowledge/server.py"
sed -i 's/from servers.skills import engine/from servers.skills import pg_engine as engine/g' "$ROOT/servers/skills/server.py"

echo "2. Menghapus engine SQLite warisan..."
rm -f "$ROOT/servers/memory/engine.py"
rm -f "$ROOT/servers/memory/hindsight_engine.py"
rm -f "$ROOT/servers/knowledge/engine.py"
rm -f "$ROOT/servers/skills/engine.py"

echo "3. Membersihkan seluruh file data lokal (.db)..."
rm -f "$ROOT/data/"*.db*

echo "4. Mencabut library aiosqlite dan sqlite-vec dari project..."
sed -i '/aiosqlite/d' "$ROOT/pyproject.toml"
sed -i '/sqlite-vec/d' "$ROOT/pyproject.toml"

echo ""
echo "✅ Finalisasi Sukses!"
echo "Seluruh agen MCP kini beroperasi secara cloud-native terpusat di PostgreSQL."
echo "Harap jalankan 'make install' suatu waktu untuk membersihkan venv bawaan dari dependensi lama (opsional)."
