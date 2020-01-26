#!/bin/bash
rm fedireads/migrations/0*
set -e
dropdb fedireads
createdb fedireads
python manage.py makemigrations fedireads
python manage.py migrate

echo "from fedireads.models import User
User.objects.create_user('mouse', 'mouse.reeve@gmail.com', 'password123')" | python manage.py shell
echo "from fedireads.models import User
User.objects.create_user('rat', 'rat@rat.com', 'ratword')" | python manage.py shell
echo "from fedireads.openlibrary import get_book
get_book(None, 'OL13549170M')
get_book(None, 'OL24738110M')" | python manage.py shell
