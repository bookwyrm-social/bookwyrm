migrate:
	docker-compose run --rm web poetry run python manage.py migrate

initdb:
	docker-compose run --rm web poetry run python manage.py initdb
