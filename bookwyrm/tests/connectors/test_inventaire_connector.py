""" testing book data connectors """
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors.inventaire import Connector


class Inventaire(TestCase):
    """test loading data from inventaire.io"""

    def setUp(self):
        """creates the connector we'll use"""
        models.Connector.objects.create(
            identifier="inventaire.io",
            name="Inventaire",
            connector_file="inventaire",
            base_url="https://inventaire.io",
            books_url="https://inventaire.io",
            covers_url="https://covers.inventaire.io",
            search_url="https://inventaire.io/search?q=",
            isbn_search_url="https://inventaire.io/isbn",
        )
        self.connector = Connector("inventaire.io")

    @responses.activate
    def test_get_book_data(self):
        """flattens the default structure to make it easier to parse"""
        responses.add(
            responses.GET,
            "https://test.url/ok",
            json={
                "entities": {
                    "isbn:9780375757853": {
                        "claims": {
                            "wdt:P31": ["wd:Q3331189"],
                        },
                        "uri": "isbn:9780375757853",
                    }
                },
                "redirects": {},
            },
        )

        result = self.connector.get_book_data("https://test.url/ok")
        self.assertEqual(result["wdt:P31"], ["wd:Q3331189"])
        self.assertEqual(result["uri"], "isbn:9780375757853")
