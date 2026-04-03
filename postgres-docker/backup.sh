#!/bin/bash
info() { echo >&2 "[$(date --iso-8601=seconds)] $*"; }

if [ "${DEBUG}" != 'false' ]; then
    info "backup: Skipping backups because DEBUG is true"
    exit 0
fi

if [ -z "$POSTGRES_DB" ]; then
    info "backup: Database not specified, defaulting to bookwyrm"
fi
if [ -z "$POSTGRES_USER" ]; then
    info "backup: Database user not specified, defaulting to bookwyrm"
fi
BACKUP_DB=${POSTGRES_DB:-bookwyrm}
BACKUP_USER=${POSTGRES_USER:-bookwyrm}
filename=backup_${BACKUP_DB}_$(date +%F)
pg_dump -U "${BACKUP_USER}" "${BACKUP_DB}" --file "/backups/$filename.sql"
info "backup: completed backup of $BACKUP_DB to /backups/$filename.sql"
