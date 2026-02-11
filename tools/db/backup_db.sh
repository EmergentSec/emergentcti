#!/usr/bin/env bash
set -euo pipefail
# Create a PostgreSQL dump backup
# Usage: bash tools/db/backup_db.sh [output_dir]

cd "$(git rev-parse --show-toplevel)"

OUTPUT_DIR="${1:-.tmp}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$OUTPUT_DIR/cti_backup_${TIMESTAMP}.sql"

echo "Backing up database to $BACKUP_FILE..."
docker compose exec -T postgres pg_dump -U cti cti > "$BACKUP_FILE"
echo "Backup complete: $BACKUP_FILE ($(wc -c < "$BACKUP_FILE") bytes)"
