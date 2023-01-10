#!/bin/bash
source /backups/.env

if [ -z "$POSTGRES_DB" ]; then
    echo "Database not specified, defaulting to bookwyrm"
fi
if [ -z "$POSTGRES_USER" ]; then
    echo "Database user not specified, defaulting to bookwyrm"
fi
BACKUP_DB=${POSTGRES_DB:-bookwyrm}
BACKUP_USER=${POSTGRES_USER:-bookwyrm}
filename=backup_${BACKUP_DB}_$(date +%F)
pg_dump -U $BACKUP_USER $BACKUP_DB > /backups/$filename.sql
