#!/bin/bash
set -e

info() { echo >&2 "[$(date --iso-8601=seconds)] $*"; }
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

    info "**** Checking if database is initialized"
    python manage.py initdb || die "Failed to initialize database"

    # after each update of assets, we run collectstatic, if it is already done, it is quick command
    # to check
    info "**** Checking static asset collection"
    python manage.py compile_themes || die "failed to compile themes"
    python manage.py collectstatic --no-input || die "failed to collect static"
    info "**** Static assets collected"
fi

exec "$@"
