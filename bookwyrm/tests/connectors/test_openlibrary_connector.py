""" testing book data connectors """
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from bookwyrm.connectors.openlibrary import Connector
from bookwyrm.connectors.openlibrary import ignore_edition
from bookwyrm.connectors.openlibrary import get_languages, get_description
from bookwyrm.connectors.openlibrary import pick_default_edition, get_openlibrary_key
from bookwyrm.connectors.connector_manager import ConnectorException

# pylint: disable=too-many-public-methods
class Openlibrary(TestCase):
    """test loading data from openlibrary.org"""

    @classmethod
    def setUpTestData(cls):
        """creates the connector in the database"""
        models.Connector.objects.create(
            identifier="openlibrary.org",
            name="OpenLibrary",
            connector_file="openlibrary",
            base_url="https://openlibrary.org",
            books_url="https://openlibrary.org",
            covers_url="https://covers.openlibrary.org",
            search_url="https://openlibrary.org/search?q=",
            isbn_search_url="https://openlibrary.org/isbn",
        )

    def setUp(self):
        """connector instance and other test data"""
        self.connector = Connector("openlibrary.org")

        work_file = pathlib.Path(__file__).parent.joinpath("../data/ol_work.json")
        edition_file = pathlib.Path(__file__).parent.joinpath("../data/ol_edition.json")
        edition_md_file = pathlib.Path(__file__).parent.joinpath(
            "../data/ol_edition_markdown.json"
        )
        edition_list_file = pathlib.Path(__file__).parent.joinpath(
            "../data/ol_edition_list.json"
        )
        self.work_data = json.loads(work_file.read_bytes())
        self.edition_data = json.loads(edition_file.read_bytes())
        self.edition_md_data = json.loads(edition_md_file.read_bytes())
        self.edition_list_data = json.loads(edition_list_file.read_bytes())

    def test_get_remote_id_from_data(self):
        """format the remote id from the data"""
        data = {"key": "/work/OL1234W"}
        result = self.connector.get_remote_id_from_data(data)
        self.assertEqual(result, "https://openlibrary.org/work/OL1234W")
        # error handling
        with self.assertRaises(ConnectorException):
            self.connector.get_remote_id_from_data({})

    def test_is_work_data(self):
        """detect if the loaded json is a work"""
        self.assertEqual(self.connector.is_work_data(self.work_data), True)
        self.assertEqual(self.connector.is_work_data(self.edition_data), False)

    @responses.activate
    def test_get_edition_from_work_data(self):
        """loads a list of editions"""
        data = {"key": "/work/OL1234W"}
        responses.add(
            responses.GET,
            "https://openlibrary.org/work/OL1234W/editions",
            json={"entries": []},
            status=200,
        )
        with patch(
            "bookwyrm.connectors.openlibrary.pick_default_edition"
        ) as pick_edition:
            pick_edition.return_value = "hi"
            result = self.connector.get_edition_from_work_data(data)
        self.assertEqual(result, "hi")

    @responses.activate
    def test_get_work_from_edition_data(self):
        """loads a list of editions"""
        data = {"works": [{"key": "/work/OL1234W"}]}
        responses.add(
            responses.GET,
            "https://openlibrary.org/work/OL1234W",
            json={"hi": "there"},
            status=200,
        )
        result = self.connector.get_work_from_edition_data(data)
        self.assertEqual(result, {"hi": "there"})

    @responses.activate
    def test_get_authors_from_data(self):
        """find authors in data"""
        responses.add(
            responses.GET,
            "https://openlibrary.org/authors/OL382982A",
            json={
                "name": "George Elliott",
                "personal_name": "George Elliott",
                "last_modified": {
                    "type": "/type/datetime",
                    "value": "2008-08-31 10:09:33.413686",
                },
                "remote_ids": {
                    "isni": "000111",
                },
                "key": "/authors/OL453734A",
                "type": {"key": "/type/author"},
                "id": 1259965,
                "revision": 2,
            },
            status=200,
        )
        results = self.connector.get_authors_from_data(self.work_data)
        result = list(results)[0]
        self.assertIsInstance(result, models.Author)
        self.assertEqual(result.name, "George Elliott")
        self.assertEqual(result.openlibrary_key, "OL453734A")
        self.assertEqual(result.isni, "000111")

    def test_get_cover_url(self):
        """formats a url that should contain the cover image"""
        blob = ["image"]
        result = self.connector.get_cover_url(blob)
        self.assertEqual(result, "https://covers.openlibrary.org/b/id/image-L.jpg")

    def test_parse_search_result(self):
        """translate json from openlibrary into SearchResult"""
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ol_search.json")
        search_data = json.loads(datafile.read_bytes())
        result = list(self.connector.parse_search_data(search_data, 0))[0]

        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, "This Is How You Lose the Time War")
        self.assertEqual(result.key, "https://openlibrary.org/works/OL20639540W")
        self.assertEqual(result.author, "Amal El-Mohtar, Max Gladstone")
        self.assertEqual(result.year, 2019)
        self.assertEqual(result.connector, self.connector)

    def test_parse_isbn_search_result(self):
        """extract the results from the search json response"""
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ol_isbn_search.json")
        search_data = json.loads(datafile.read_bytes())
        result = list(self.connector.parse_isbn_search_data(search_data))
        self.assertEqual(len(result), 1)

        result = result[0]
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, "Les ombres errantes")
        self.assertEqual(result.key, "https://openlibrary.org/books/OL16262504M")
        self.assertEqual(result.author, "Pascal Quignard")
        self.assertEqual(result.year, "2002")
        self.assertEqual(result.connector, self.connector)

    @responses.activate
    def test_load_edition_data(self):
        """format url from key and make request"""
        key = "OL1234W"
        responses.add(
            responses.GET,
            "https://openlibrary.org/works/OL1234W/editions",
            json={"hi": "there"},
        )
        result = self.connector.load_edition_data(key)
        self.assertEqual(result, {"hi": "there"})

    @responses.activate
    def test_expand_book_data(self):
        """given a book, get more editions"""
        work = models.Work.objects.create(title="Test Work", openlibrary_key="OL1234W")
        edition = models.Edition.objects.create(title="Test Edition", parent_work=work)

        responses.add(
            responses.GET,
            "https://openlibrary.org/works/OL1234W/editions",
            json={"entries": []},
        )
        with patch(
            "bookwyrm.connectors.abstract_connector.AbstractConnector."
            "create_edition_from_data"
        ):
            self.connector.expand_book_data(edition)
            self.connector.expand_book_data(work)

    def test_get_description(self):
        """should do some cleanup on the description data"""
        description = get_description(self.work_data["description"])
        expected = "First in the Old Kingdom/Abhorsen series."
        self.assertEqual(description, expected)

    def test_get_description_markdown_paragraphs(self):
        """should do some cleanup on the description data"""
        description = get_description("Paragraph 1\n\nParagraph 2")
        expected = "<p>Paragraph 1</p>\n<p>Paragraph 2</p>"
        self.assertEqual(description, expected)

    def test_get_description_markdown_blockquote(self):
        """should do some cleanup on the description data"""
        description = get_description("> Quote\n\nParagraph 2")
        expected = "<blockquote>\n<p>Quote</p>\n</blockquote>\n<p>Paragraph 2</p>"
        self.assertEqual(description, expected)

    def test_get_openlibrary_key(self):
        """extracts the uuid"""
        key = get_openlibrary_key("/books/OL27320736M")
        self.assertEqual(key, "OL27320736M")

    def test_get_languages(self):
        """looks up languages from a list"""
        languages = get_languages(self.edition_data["languages"])
        self.assertEqual(languages, ["English"])

    def test_pick_default_edition(self):
        """detect if the loaded json is an edition"""
        edition = pick_default_edition(self.edition_list_data["entries"])
        self.assertEqual(edition["key"], "/books/OL9788823M")

    @responses.activate
    def test_create_edition_from_data(self):
        """okay but can it actually create an edition with proper metadata"""
        work = models.Work.objects.create(title="Hello")
        responses.add(
            responses.GET,
            "https://openlibrary.org/authors/OL382982A",
            json={"hi": "there"},
            status=200,
        )
        with patch(
            "bookwyrm.connectors.openlibrary.Connector.get_authors_from_data"
        ) as mock:
            mock.return_value = []
            result = self.connector.create_edition_from_data(work, self.edition_data)
        self.assertEqual(result.parent_work, work)
        self.assertEqual(result.title, "Sabriel")
        self.assertEqual(result.isbn_10, "0060273224")
        self.assertEqual(result.description, self.edition_data["description"]["value"])
        self.assertEqual(result.languages[0], "English")
        self.assertEqual(result.publishers[0], "Harper Trophy")
        self.assertEqual(result.pages, 491)
        self.assertEqual(result.subjects[0], "Fantasy.")
        self.assertEqual(result.physical_format, "Hardcover")

    @responses.activate
    def test_create_edition_markdown_from_data(self):
        """okay but can it actually create an edition with proper metadata"""
        work = models.Work.objects.create(title="Hello")
        responses.add(
            responses.GET,
            "https://openlibrary.org/authors/OL10183984A",
            json={"hi": "there"},
            status=200,
        )
        with patch(
            "bookwyrm.connectors.openlibrary.Connector.get_authors_from_data"
        ) as mock:
            mock.return_value = []
            result = self.connector.create_edition_from_data(work, self.edition_md_data)
        self.assertEqual(
            result.description,
            '<blockquote>\n<p>"She didn\'t choose her garden" opens this chapbook '
            "exploring Black womanhood, mental and physical health, spirituality, and "
            "ancestral roots. It is an investigation of how to locate a self amidst "
            "complex racial history and how to forge an authentic way forward. There's "
            "internal slippage as the subject weaves between the presence and spirits "
            "of others, as well as a reckoning with the toll of navigating this world "
            "as a Black woman. Yet, we also see hopefulness: a refuge in becoming part "
            "of the collective, beyond individuality. <em>The Stars With You</em> "
            "gives us a speculative yearning for what is to come and probes what is "
            "required to reach it.</p>\n</blockquote>\n<ul>\n<li><a "
            'href="https://store.cooperdillon.com/product/the-stars-with-you-by-'
            'stefani-cox">publisher</a></li>\n</ul>',
        )

    def test_ignore_edition(self):
        """skip editions with poor metadata"""
        self.assertFalse(ignore_edition({"isbn_13": "hi"}))
        self.assertFalse(ignore_edition({"oclc_numbers": "hi"}))
        self.assertFalse(ignore_edition({"covers": "hi"}))
        self.assertFalse(ignore_edition({"languages": "languages/fr"}))
        self.assertTrue(ignore_edition({"languages": "languages/eng"}))
        self.assertTrue(ignore_edition({"format": "paperback"}))

    def test_remote_id_from_model(self):
        """figure out a url from an id"""
        obj = models.Author.objects.create(
            name="George Elliott", openlibrary_key="OL453734A"
        )
        self.assertEqual(
            self.connector.get_remote_id_from_model(obj),
            "https://openlibrary.org/authors/OL453734A",
        )
