#!/usr/bin/env bash
# Backup SQLite knowledge, memory and skills databases.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT/data"
BACKUP_DIR="$ROOT/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

for db in memory_v2.db knowledge_v2.db skills_v2.db; do
    src="$DATA_DIR/$db"
    if [[ -f "$src" ]]; then
        dest="$BACKUP_DIR/${db%.db}_${TIMESTAMP}.db"
        cp "$src" "$dest"
        echo "Backed up $db -> $dest"
    fi
done

echo "Backup complete: $BACKUP_DIR"
