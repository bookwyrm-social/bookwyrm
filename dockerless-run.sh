#!/bin/bash

# stop if one process fails
set -e

# bookwyrm
/opt/bookwyrm/venv/bin/gunicorn bookwyrm.wsgi:application --bind 0.0.0.0:8000 &

# bookwyrm - no nginx (w/ debug enabled)
# /opt/bookwyrm/venv/bin/python3 /opt/bookwyrm/manage.py runserver 0.0.0.0:8000 &

# celery + flower
/opt/bookwyrm/venv/bin/celery -A celerywyrm worker -l info -Q high_priority,medium_priority,low_priority &
/opt/bookwyrm/venv/bin/celery -A celerywyrm beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
/opt/bookwyrm/venv/bin/celery -A celerywyrm flower &
