#!/bin/bash
set -e

# We mark migration-hash file to tell if database is initialized and
# should we print out the admin code or not
CANARY=/app/static/.dbinit_runned

info() { echo >&2 "$*"; }
die() {
    echo >&2 "$*"
    exit 1
}

trap exit TERM

# web container is running gunicorn, so we know to use that for migrations/init-db
# other containers (celery, celery-beat, etc) just run their commands and are started
# after web-container as depends_on in docker-compose.yml
if [ "$1" = "gunicorn" ]; then
    # we run all the migrations if needed, it is no-op if none needed
    info "**** Checking needed migrations"
    python manage.py migrate || die "failed to migrate"
    python manage.py migrate django_celery_beat || die "failed to migrate django"
    info "**** Migrations done"

    # after each update of assets, we run collectstatic, if it is already done, it is quick command
    # to check
    info "**** Checking static asset collection"
    python manage.py compile_themes || die "failed to compile themes"
    python manage.py collectstatic --no-input || die "failed to collect static"
    info "**** Static assets collected"

    # If no canary-file, we know that datatbase is not initialized,
    # we could safely run initdb again, but we don't want to print
    # unnecessary admin code to logs on every restart or mention initial database population
    # unnecessarily
    if [ ! -r "$CANARY" ]; then
        info "**** Doing initial database population"
        python manage.py initdb || die "failed to initdb"
    fi
    # We are running container as non-root id, so check that permissions are correct
    info "**** Checking images and exports directory permissions to be correct"
    chown -c -R bookwyrm /app/exports
    chown -c -R bookwyrm /app/images
    chown -c -R bookwyrm /app/static/css/themes

    # if no canary file, output admin_code for initial admin user, maybe this should be done some
    # other way?
    if [ ! -r "$CANARY" ]; then
        python manage.py admin_code
        info "**** Done with initial setup"
    fi

    # create canary-file and include the current migration hash created in Dockerfile build
    info "**** Marking database as initialized"
    echo "yes" >"$CANARY"
fi

exec gosu bookwyrm "$@"
