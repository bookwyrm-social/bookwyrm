""" testing book data connectors """
import json
import pathlib
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors.inventaire import Connector, get_language_code


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

    def test_format_search_result(self):
        """json to search result objs"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        results = self.connector.parse_search_data(search_results)
        formatted = self.connector.format_search_result(results[0])

        self.assertEqual(formatted.title, "The Stories of Vladimir Nabokov")
        self.assertEqual(
            formatted.key, "https://inventaire.io?action=by-uris&uris=wd:Q7766679"
        )
        self.assertEqual(
            formatted.cover,
            "https://covers.inventaire.io/img/entities/ddb32",
        )

    def test_get_cover_url(self):
        """figure out where the cover image is"""
        cover_blob = {"url": "/img/entities/d46a8"}
        result = self.connector.get_cover_url(cover_blob)
        self.assertEqual(result, "https://covers.inventaire.io/img/entities/d46a8")

        cover_blob = {
            "url": "https://commons.wikimedia.org/wiki/d.jpg?width=1000",
            "file": "The Moonstone 1st ed.jpg",
            "credits": {
                "text": "Wikimedia Commons",
                "url": "https://commons.wikimedia.org/wiki/File:The Moonstone.jpg",
            },
        }

        result = self.connector.get_cover_url(cover_blob)
        self.assertEqual(
            result,
            "https://commons.wikimedia.org/wiki/d.jpg?width=1000",
        )

    @responses.activate
    def test_resolve_keys(self):
        """makes an http request"""
        responses.add(
            responses.GET,
            "https://inventaire.io?action=by-uris&uris=wd:Q465821",
            json={
                "entities": {
                    "wd:Q465821": {
                        "type": "genre",
                        "labels": {
                            "nl": "briefroman",
                            "en": "epistolary novel",
                            "de-ch": "Briefroman",
                            "en-ca": "Epistolary novel",
                            "nb": "brev- og dagbokroman",
                        },
                        "descriptions": {
                            "en": "novel written as a series of documents",
                            "es": "novela escrita como una serie de documentos",
                            "eo": "romano en la formo de serio de leteroj",
                        },
                    },
                    "redirects": {},
                }
            },
        )
        responses.add(
            responses.GET,
            "https://inventaire.io?action=by-uris&uris=wd:Q208505",
            json={
                "entities": {
                    "wd:Q208505": {
                        "type": "genre",
                        "labels": {
                            "en": "crime novel",
                        },
                    },
                }
            },
        )

        keys = [
            "wd:Q465821",
            "wd:Q208505",
        ]
        result = self.connector.resolve_keys(keys)
        self.assertEqual(result, ["epistolary novel", "crime novel"])

    def test_isbn_search(self):
        """another search type"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_isbn_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        results = self.connector.parse_isbn_search_data(search_results)
        formatted = self.connector.format_isbn_search_result(results[0])

        self.assertEqual(formatted.title, "L'homme aux cercles bleus")
        self.assertEqual(
            formatted.key,
            "https://inventaire.io?action=by-uris&uris=isbn:9782290349229",
        )
        self.assertEqual(
            formatted.cover,
            "https://covers.inventaire.io/img/entities/12345",
        )

    def test_get_language_code(self):
        """get english or whatever is in reach"""
        options = {
            "de": "bip",
            "en": "hi",
            "fr": "there",
        }
        self.assertEqual(get_language_code(options), "hi")

        options = {
            "fr": "there",
        }
        self.assertEqual(get_language_code(options), "there")
        self.assertIsNone(get_language_code({}))
