#!/bin/bash
# Perform initial setup so that the users don't have to
# This should only be done in the web container;
# the celery and flower containers should wait for the canary to exist

CANARY=/app/static/.dbinit_done

info() { echo >&2 "$*" ; }
die() { echo >&2 "$*" ; exit 1 ; }

if [ "$1" == "exit" ]; then
	info "**** base container exiting"
	exit 0
fi

if [ -z "$DB_INIT" ]; then
	while [ ! -r "$CANARY" ]; do
		info "**** Waiting for database and migrations to finish"
		sleep 10
	done
elif [ ! -r "$CANARY" ]; then
	info "**** Doing initial setup!"
	python manage.py migrate || die "failed to migrate"
	python manage.py migrate django_celery_beat || die "failed to migrate django"
	python manage.py initdb || die "failed to initdb"
	python manage.py collectstatic --no-input || die "failed to collect static"
        python manage.py admin_code

	info "**** Done with initial setup!"
	touch "$CANARY"
fi

exec bash -c "$*"
