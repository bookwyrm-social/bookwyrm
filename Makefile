.PHONY: itblack

itblack:
	docker-compose run --rm web black celerywyrm
	docker-compose run --rm web black bookwyrm