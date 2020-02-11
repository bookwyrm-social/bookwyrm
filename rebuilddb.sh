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
User.objects.create_user('rat', 'rat@rat.com', 'ratword')
User.objects.get(id=1).followers.add(User.objects.get(id=2))" | python manage.py shell
echo "from fedireads.openlibrary import get_or_create_book
get_or_create_book('OL1715344W')
get_or_create_book('OL102749W')" | python manage.py shell
python manage.py runserver
