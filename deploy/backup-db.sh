#!/bin/sh
set -eu

umask 077

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

COMPOSE_FILE=${COMPOSE_FILE:-"$ROOT_DIR/compose.staging.yml"}
ENV_FILE=${ENV_FILE:-"$ROOT_DIR/deploy/staging.env"}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/cs2-performance-lab}
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}

case "$RETENTION_DAYS" in
    ''|*[!0-9]*)
        echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
        exit 1
        ;;
esac

if [ ! -f "$ENV_FILE" ]; then
    echo "Staging env file not found: $ENV_FILE" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

LOCK_DIR="$BACKUP_DIR/.backup.lock"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another database backup is already running" >&2
    exit 1
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FINAL_FILE="$BACKUP_DIR/cs2_${STAMP}_$$.dump"
TEMP_FILE="${FINAL_FILE}.tmp"

cleanup() {
    rm -f "$TEMP_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT HUP INT TERM

echo "Creating PostgreSQL backup..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    exec -T db \
    sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
    > "$TEMP_FILE"

if [ ! -s "$TEMP_FILE" ]; then
    echo "Backup is empty" >&2
    exit 1
fi

echo "Checking dump structure..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    exec -T db \
    pg_restore -l \
    < "$TEMP_FILE" \
    > /dev/null

mv "$TEMP_FILE" "$FINAL_FILE"
chmod 600 "$FINAL_FILE"

find "$BACKUP_DIR" \
    -type f \
    -name 'cs2_*.dump' \
    -mtime "+$RETENTION_DAYS" \
    -delete

SIZE=$(wc -c < "$FINAL_FILE" | tr -d ' ')

echo "Backup complete"
echo "File: $FINAL_FILE"
echo "Bytes: $SIZE"
echo "Retention: $RETENTION_DAYS days"
