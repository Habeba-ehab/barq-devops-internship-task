#!/usr/bin/env bash
set -euo pipefail

# Restores a PostgreSQL backup created by backup.sh.
# Usage: ./restore.sh <backup_file>

PROJECT="barq-assessment"
CONTAINER="postgres"
DB_USER="barq_app"
DB_NAME="barq_tasks"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>" >&2
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "Checking that container '$CONTAINER' is running..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container '$CONTAINER' is not running." >&2
    exit 1
fi

echo "Restoring '$BACKUP_FILE' into database '$DB_NAME'..."
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE" > /tmp/restore_output.log 2>&1 || {
    echo "ERROR: restore failed. Output:" >&2
    cat /tmp/restore_output.log >&2
    exit 1
}

echo "Restore complete."

echo "Verifying restored data (row count in a known table if present)..."
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM records;" | xargs echo "records table row count:"