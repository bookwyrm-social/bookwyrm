#!/bin/bash
set -e

CANARY=/app/static/.dbmigration_hash

info() { echo >&2 "$*"; }
die() {
    echo >&2 "$*"
    exit 1
}

trap exit TERM

WANTED_HASH=$(</build_migration_hash)

if [ "$1" = "gunicorn" ]; then
    info "**** Checking needed migrations"
    python manage.py migrate || die "failed to migrate"
    python manage.py migrate django_celery_beat || die "failed to migrate django"
    info "**** Migrations done"
    info "**** Checking static asset collection"
    python manage.py collectstatic --no-input || die "failed to collect static"
    info "**** Static assets collected"
    if [ ! -r "$CANARY" ]; then
        info "**** Doing initial database population"
        python manage.py initdb || die "failed to initdb"
    fi
    info "**** Checking images and exports directory permissions to be correct"
    chown -c -R bookwyrm /app/exports
    chown -c -R bookwyrm /app/images
    chown -c -R bookwyrm /app/static/css/themes
    if [ ! -r "$CANARY" ]; then
        python manage.py admin_code
        info "**** Done with initial setup"
    fi

    info "**** Marking migrations handled with hash ${WANTED_HASH}"
    echo "$WANTED_HASH" >"$CANARY"
else
    while [ "$(grep -s -e "$WANTED_HASH" "$CANARY")x" = "x" ]; do
        info "**** Waiting for database and migrations to finish"
        sleep 3
    done
    info "**** Migrations handled, starting service"
fi

exec gosu bookwyrm "$@"
