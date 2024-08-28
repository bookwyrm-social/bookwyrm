""" testing book data connectors """
import json
import pathlib
from django.test import TestCase

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from bookwyrm.connectors.bookwyrm_connector import Connector


class BookWyrmConnector(TestCase):
    """this connector doesn't do much, just search"""

    @classmethod
    def setUpTestData(cls):
        """create bookwrym_connector in the database"""
        models.Connector.objects.create(
            identifier="example.com",
            connector_file="bookwyrm_connector",
            base_url="https://example.com",
            books_url="https://example.com",
            covers_url="https://example.com/images/covers",
            search_url="https://example.com/search?q=",
        )

    def setUp(self):
        """test data"""
        self.connector = Connector("example.com")

    def test_get_or_create_book_existing(self):
        """load book activity"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(title="Test Edition", parent_work=work)
        result = self.connector.get_or_create_book(book.remote_id)
        self.assertEqual(book, result)

    def test_parse_search_data(self):
        """create a SearchResult object from search response json"""
        datafile = pathlib.Path(__file__).parent.joinpath("../data/bw_search.json")
        search_data = json.loads(datafile.read_bytes())
        result = list(self.connector.parse_search_data(search_data, 0))[0]
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, "Jonathan Strange and Mr Norrell")
        self.assertEqual(result.key, "https://example.com/book/122")
        self.assertEqual(result.author, "Susanna Clarke")
        self.assertEqual(result.year, 2017)
        self.assertEqual(result.connector, self.connector)

    def test_parse_isbn_search_data(self):
        """just gotta attach the connector"""
        datafile = pathlib.Path(__file__).parent.joinpath("../data/bw_search.json")
        search_data = json.loads(datafile.read_bytes())
        result = list(self.connector.parse_isbn_search_data(search_data))[0]
        self.assertEqual(result.connector, self.connector)
