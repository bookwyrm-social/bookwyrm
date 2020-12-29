#!/bin/bash

set -e

function echo_header {
  echo -e "\e[1m\e[4m\n$1\e[0m"
}

source .env

echo_header "Checking current migration status..."
LAST_MIGRATION=$(docker-compose exec db psql -U ${POSTGRES_USER} ${POSTGRES_DB} -t -c "SELECT name FROM django_migrations WHERE app='bookwyrm' ORDER BY applied DESC LIMIT 1" | tr -d '[:blank:]\r\n')
if [ -f bookwyrm/migrations/$LAST_MIGRATION.py ]; then
  echo "You seem to be up to date, so...if it ain't broke, don't fix it!"
  echo "If it is broke, this script probably can't help you, sorry!"
  exit 0
fi

echo_header "Resetting to before the migration merge..."
ORIGINAL_COMMIT=$(git rev-parse --abbrev-ref HEAD)
git stash
git checkout ce5d8
echo_header "Migrating to catch up from where we were at ($LAST_MIGRATION)..."
./fr-dev migrate
echo_header "Jumping back to $ORIGINAL_COMMIT..."
git checkout $ORIGINAL_COMMIT
git stash pop
echo_header "Patching up our migration history..."
docker-compose exec web python manage.py migrate bookwyrm 0006 --fake
echo_header "Catching up on migrations after the migration merge..."
./fr-dev migrate
echo_header "All done! Should be good to go now"
