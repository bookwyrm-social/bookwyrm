""" Add finna connector to connectors """
from django.core.management.base import BaseCommand

from bookwyrm import models


def enable_finna_connector():

    models.Connector.objects.create(
        identifier="api.finna.fi",
        name="Finna API",
        connector_file="finna",
        base_url="https://www.finna.fi",
        books_url="https://api.finna.fi/api/v1/record" "?id=",
        covers_url="https://api.finna.fi",
        search_url="https://api.finna.fi/api/v1/search?limit=20"
        "&filter[]=format%3a%220%2fBook%2f%22"
        "&field[]=title&field[]=recordPage&field[]=authors"
        "&field[]=year&field[]=id&field[]=formats&field[]=images"
        "&lookfor=",
        isbn_search_url="https://api.finna.fi/api/v1/search?limit=1"
        "&filter[]=format%3a%220%2fBook%2f%22"
        "&field[]=title&field[]=recordPage&field[]=authors&field[]=year"
        "&field[]=id&field[]=formats&field[]=images"
        "&lookfor=isbn:",
    )


def remove_finna_connector():
    models.Connector.objects.filter(identifier="api.finna.fi").update(
        active=False, deactivation_reason="Disabled by management command"
    )
    print("Finna connector deactivated")


# pylint: disable=no-self-use
# pylint: disable=unused-argument
class Command(BaseCommand):
    """command-line options"""

    help = "Setup Finna API connector"

    def add_arguments(self, parser):
        """specify argument to remove connector"""
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate the finna connector from config",
        )

    def handle(self, *args, **options):
        """enable or remove connector"""
        if options.get("deactivate"):
            print("Deactivate finna connector config if one present")
            remove_finna_connector()
        else:
            print("Adding Finna API connector to configuration")
            enable_finna_connector()
