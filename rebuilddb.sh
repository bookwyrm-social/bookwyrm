#!/bin/bash
set -e

if [ ! -f .env ]; then
  echo "No .env found -- copying .example.env to .env!"
  cp .env.example .env
fi

source .env

if [ $BOOKWYRM_DATABASE_BACKEND = 'sqlite' ]; then
  if [ -f fedireads.db ]; then
    rm fedireads.db
  fi
else
  # assume postgres
  dropdb fedireads
  createdb fedireads
fi

python manage.py makemigrations fedireads
python manage.py migrate

python manage.py shell < init_db.py
python manage.py runserver
