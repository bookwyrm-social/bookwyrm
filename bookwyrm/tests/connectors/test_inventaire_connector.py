""" testing book data connectors """
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors.inventaire import Connector, get_language_code
from bookwyrm.connectors.connector_manager import ConnectorException


class Inventaire(TestCase):
    """test loading data from inventaire.io"""

    @classmethod
    def setUpTestData(cls):
        """creates the connector in the database"""
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

    def setUp(self):
        """connector instance"""
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

    @responses.activate
    def test_get_book_data_invalid(self):
        """error if there isn't any entity data"""
        responses.add(
            responses.GET,
            "https://test.url/ok",
            json={
                "entities": {},
                "redirects": {},
            },
        )

        with self.assertRaises(ConnectorException):
            self.connector.get_book_data("https://test.url/ok")

    def test_parse_search_data(self):
        """json to search result objs"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_search_data(search_results, 0))[0]

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

    def test_pase_isbn_search_data(self):
        """another search type"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_isbn_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_isbn_search_data(search_results))[0]

        self.assertEqual(formatted.title, "L'homme aux cercles bleus")
        self.assertEqual(
            formatted.key,
            "https://inventaire.io?action=by-uris&uris=isbn:9782290349229",
        )
        self.assertEqual(
            formatted.cover,
            "https://covers.inventaire.io/img/entities/12345",
        )

    def test_parse_isbn_search_data_empty(self):
        """another search type"""
        search_results = {}
        results = list(self.connector.parse_isbn_search_data(search_results))
        self.assertEqual(results, [])

    def test_is_work_data(self):
        """is it a work"""
        work_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_work.json"
        )
        work_data = json.loads(work_file.read_bytes())
        with patch("bookwyrm.connectors.inventaire.get_data") as get_data_mock:
            get_data_mock.return_value = work_data
            formatted = self.connector.get_book_data("hi")
        self.assertTrue(self.connector.is_work_data(formatted))

        edition_file = pathlib.Path(__file__).parent.joinpath(
            "../data/inventaire_edition.json"
        )
        edition_data = json.loads(edition_file.read_bytes())
        with patch("bookwyrm.connectors.inventaire.get_data") as get_data_mock:
            get_data_mock.return_value = edition_data
            formatted = self.connector.get_book_data("hi")
        self.assertFalse(self.connector.is_work_data(formatted))

    @responses.activate
    def test_get_edition_from_work_data(self):
        """load edition"""
        responses.add(
            responses.GET,
            "https://inventaire.io/?action=by-uris&uris=hello",
            json={"entities": {}},
        )
        data = {"uri": "blah"}
        with (
            patch(
                "bookwyrm.connectors.inventaire.Connector.load_edition_data"
            ) as loader_mock,
            patch(
                "bookwyrm.connectors.inventaire.Connector.get_book_data"
            ) as getter_mock,
        ):
            loader_mock.return_value = {"uris": ["hello"]}
            self.connector.get_edition_from_work_data(data)
        self.assertTrue(getter_mock.called)

        with patch(
            "bookwyrm.connectors.inventaire.Connector.load_edition_data"
        ) as loader_mock:
            loader_mock.return_value = {"uris": []}
            with self.assertRaises(ConnectorException):
                self.connector.get_edition_from_work_data(data)

    @responses.activate
    def test_get_work_from_edition_data(self):
        """load work"""
        responses.add(
            responses.GET,
            "https://inventaire.io/?action=by-uris&uris=hello",
        )
        data = {"wdt:P629": ["hello"]}
        with patch("bookwyrm.connectors.inventaire.Connector.get_book_data") as mock:
            self.connector.get_work_from_edition_data(data)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], "https://inventaire.io?action=by-uris&uris=hello")

        data = {"wdt:P629": [None]}
        with self.assertRaises(ConnectorException):
            self.connector.get_work_from_edition_data(data)

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

    @responses.activate
    def test_get_description(self):
        """extract a wikipedia excerpt"""
        responses.add(
            responses.GET,
            "https://inventaire.io/api/data?action=wp-extract&lang=en&title=test_path",
            json={"extract": "hi hi"},
        )

        extract = self.connector.get_description(
            {"enwiki": {"title": "test_path", "badges": "hello"}}
        )
        self.assertEqual(extract, "hi hi")

    def test_remote_id_from_model(self):
        """figure out a url from an id"""
        obj = models.Author.objects.create(name="hello", inventaire_id="123")
        self.assertEqual(
            self.connector.get_remote_id_from_model(obj),
            "https://inventaire.io?action=by-uris&uris=123",
        )
