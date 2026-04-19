#!/usr/bin/env bash
#
# backup_db.sh - PostgreSQL backup script for IATM Conference Management Tool
#
# Creates timestamped, gzip-compressed pg_dump backups, removes old ones,
# and logs every step. Designed to run standalone, from cron, or in Docker.
#
# Usage:
#   ./backup_db.sh                   # uses defaults / env vars
#   BACKUP_DIR=/mnt/nfs/backups RETENTION_DAYS=7 ./backup_db.sh
#
# Required tool: pg_dump (provided by postgresql-client or the postgres image)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration  (override any of these with environment variables)
# ---------------------------------------------------------------------------
DB_NAME="${DB_NAME:-iatm_conference_db}"
DB_USER="${DB_USER:-iatm_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"
LOG_PREFIX="[backup_db]"

log()  { echo "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') $*"; }
die()  { log "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
command -v pg_dump >/dev/null 2>&1 || die "pg_dump not found. Install postgresql-client."

if [ ! -d "${BACKUP_DIR}" ]; then
    log "Creating backup directory: ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}" || die "Cannot create ${BACKUP_DIR}"
fi

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
log "Starting backup of database '${DB_NAME}' on ${DB_HOST}:${DB_PORT}"

export PGPASSWORD="${DB_PASSWORD}"

if pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --format=custom \
    --compress=6 \
    --no-owner \
    --no-privileges \
    "${DB_NAME}" > "${BACKUP_FILE}"; then

    unset PGPASSWORD
    SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
    log "Backup complete: ${BACKUP_FILE} (${SIZE})"
else
    unset PGPASSWORD
    rm -f "${BACKUP_FILE}"
    die "pg_dump failed"
fi

# ---------------------------------------------------------------------------
# Retention: delete backups older than RETENTION_DAYS
# ---------------------------------------------------------------------------
log "Pruning backups older than ${RETENTION_DAYS} days in ${BACKUP_DIR}"

DELETED=0
while IFS= read -r -d '' old_file; do
    log "  Removing old backup: ${old_file}"
    rm -f "${old_file}"
    DELETED=$((DELETED + 1))
done < <(find "${BACKUP_DIR}" -maxdepth 1 -name "${DB_NAME}_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -print0 2>/dev/null)

log "Pruned ${DELETED} old backup(s)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL="$(find "${BACKUP_DIR}" -maxdepth 1 -name "${DB_NAME}_*.sql.gz" -type f 2>/dev/null | wc -l | tr -d ' ')"
log "Done. ${TOTAL} backup(s) currently in ${BACKUP_DIR}"
