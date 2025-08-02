#!/bin/bash
set -e

CANARY=/app/static/.dbmigration_timestamp

info() { echo >&2 "$*"; }
die() {
    echo >&2 "$*"
    exit 1
}

trap exit TERM

WANTED_TIMESTAMP=$(</build_timestamp)

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
    if [ ! -r "$CANARY" ]; then
        python manage.py admin_code
        info "**** Done with initial setup"
    fi

    info "**** Marking migrations handled with timestamp ${WANTED_TIMESTAMP}"
    echo "$WANTED_TIMESTAMP" >"$CANARY"
else
    while [ "$(grep -s -e "$WANTED_TIMESTAMP" "$CANARY")x" = "x" ]; do
        info "**** Waiting for database and migrations to finish"
        sleep 3
    done
    info "**** Migrations handled, starting service"
fi

exec gosu bookwyrm "$@"
