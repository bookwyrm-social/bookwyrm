#!/bin/bash
if [ -z "$POSTGRES_DB" ]; then
    echo "Database not specified, defaulting to bookwyrm"
fi
BACKUP_DB=${POSTGRES_DB:-bookwyrm}
filename=backup__$(date +%F)
pg_dump -U $BACKUP_DB > /backups/$filename.sql
