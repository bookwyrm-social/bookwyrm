"""Add Libris connector to connectors"""

from django.core.management.base import BaseCommand

from bookwyrm import models


def enable_libris_connector():
    models.Connector.objects.create(
        identifier="libris.kb.se",
        name="Libris",
        connector_file="libris",
        base_url="https://libris.kb.se",
        books_url="http://libris.kb.se/xsearch?format=json&format_level=full&n=1&query=",
        covers_url="https://libris.kb.se",
        search_url="http://libris.kb.se/xsearch?format=json&format_level=full&n=20&query=",
        isbn_search_url="http://libris.kb.se/xsearch?format=json&format_level=full&n=5&query=isbn:",
    )


def remove_libris_connector():
    models.Connector.objects.filter(identifier="libris.kb.se").update(
        active=False, deactivation_reason="Disabled by management command"
    )
    print("Libris connector deactivated")


class Command(BaseCommand):
    """command-line options"""

    help = "Setup Libris API connector"

    def add_arguments(self, parser):
        """specify argument to remove connector"""
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate the Libris connector from config",
        )

    def handle(self, *args, **options):
        """enable or remove connector"""
        if options.get("deactivate"):
            print("Deactivate Libris connector config if one present")
            remove_libris_connector()
        else:
            print("Adding Libris API connector to configuration")
            enable_libris_connector()
