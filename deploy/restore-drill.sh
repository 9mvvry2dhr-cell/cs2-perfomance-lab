#!/bin/sh
set -eu

umask 077

BACKUP_FILE=${1:-}
POSTGRES_IMAGE=${RESTORE_POSTGRES_IMAGE:-postgres:17-alpine}

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 /path/to/backup.dump" >&2
    exit 1
fi

if [ ! -s "$BACKUP_FILE" ]; then
    echo "Backup file not found or empty: $BACKUP_FILE" >&2
    exit 1
fi

CONTAINER="cs2-restore-drill-$$"
VOLUME="cs2_restore_drill_$$"
DB_NAME="restore_test"
DB_USER="restore_user"
DB_PASSWORD="restore_drill_only"

cleanup() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    docker volume rm -f "$VOLUME" >/dev/null 2>&1 || true
}

trap cleanup EXIT HUP INT TERM

echo "Checking dump archive..."

docker run \
    --rm \
    --network none \
    -i \
    --entrypoint pg_restore \
    "$POSTGRES_IMAGE" \
    -l \
    < "$BACKUP_FILE" \
    > /dev/null

echo "Creating isolated PostgreSQL restore target..."

docker volume create "$VOLUME" > /dev/null

docker run \
    -d \
    --name "$CONTAINER" \
    --network none \
    -e POSTGRES_DB="$DB_NAME" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -v "$VOLUME:/var/lib/postgresql/data" \
    "$POSTGRES_IMAGE" \
    > /dev/null

READY=0
ATTEMPT=1

while [ "$ATTEMPT" -le 30 ]; do
    if docker exec "$CONTAINER" \
        pg_isready -U "$DB_USER" -d "$DB_NAME" \
        > /dev/null 2>&1
    then
        READY=1
        break
    fi

    sleep 1
    ATTEMPT=$((ATTEMPT + 1))
done

if [ "$READY" -ne 1 ]; then
    echo "Restore PostgreSQL did not become ready" >&2
    docker logs "$CONTAINER" >&2 || true
    exit 1
fi

docker cp \
    "$BACKUP_FILE" \
    "$CONTAINER:/tmp/restore.dump" \
    > /dev/null

echo "Restoring backup..."

docker exec \
    "$CONTAINER" \
    pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    /tmp/restore.dump

REVISION=$(docker exec \
    "$CONTAINER" \
    psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Atc \
    "select version_num from alembic_version;")

TABLES=$(docker exec \
    "$CONTAINER" \
    psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Atc \
    "select count(*) from information_schema.tables where table_schema='public';")

MATCHES=$(docker exec \
    "$CONTAINER" \
    psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Atc \
    "select count(*) from matches;")

case "$TABLES" in
    ''|*[!0-9]*|0)
        echo "Restored database contains no public tables" >&2
        exit 1
        ;;
esac

case "$MATCHES" in
    ''|*[!0-9]*)
        echo "Could not verify restored matches table" >&2
        exit 1
        ;;
esac

echo "Restore drill passed"
echo "Alembic: $REVISION"
echo "Public tables: $TABLES"
echo "Matches: $MATCHES"
echo "Temporary restore resources will now be removed"
