#!/usr/bin/env bash
set -euo pipefail

# Backs up the PostgreSQL database to a timestamped SQL dump file.
# Usage: ./backup.sh [output_dir]

PROJECT="barq-assessment"
CONTAINER="postgres"
DB_USER="barq_app"
DB_NAME="barq_tasks"
OUTPUT_DIR="${1:-./backups}"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_FILE="${OUTPUT_DIR}/backup_${TIMESTAMP}.sql"

echo "Checking that container '$CONTAINER' is running..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container '$CONTAINER' is not running." >&2
    exit 1
fi

echo "Backing up database '$DB_NAME' from container '$CONTAINER'..."
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: backup file is empty, something went wrong." >&2
    exit 1
fi

LINES=$(wc -l < "$BACKUP_FILE")
echo "Backup complete: $BACKUP_FILE ($LINES lines)"
echo "$BACKUP_FILE"