""" test searching for books """
import datetime
from django.test import TestCase
from django.utils import timezone

from bookwyrm import book_search, models
from bookwyrm.connectors.abstract_connector import AbstractMinimalConnector


class BookSearch(TestCase):
    """look for some books"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.work = models.Work.objects.create(title="Example Work")

        self.first_edition = models.Edition.objects.create(
            title="Example Edition",
            parent_work=self.work,
            isbn_10="0000000000",
            physical_format="Paperback",
            published_date=datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc),
        )
        self.second_edition = models.Edition.objects.create(
            title="Another Edition",
            parent_work=self.work,
            isbn_10="1111111111",
            openlibrary_key="hello",
        )

    def test_search(self):
        """search for a book in the db"""
        # title/author
        results = book_search.search("Example")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

        # isbn
        results = book_search.search("0000000000")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

        # identifier
        results = book_search.search("hello")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_isbn_search(self):
        """test isbn search"""
        results = book_search.isbn_search("0000000000")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

    def test_search_identifiers(self):
        """search by unique identifiers"""
        results = book_search.search_identifiers("hello")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_search_title_author(self):
        """search by unique identifiers"""
        results = book_search.search_title_author("Another", min_confidence=0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_format_search_result(self):
        """format a search result"""
        result = book_search.format_search_result(self.first_edition)
        self.assertEqual(result["title"], "Example Edition")
        self.assertEqual(result["key"], self.first_edition.remote_id)
        self.assertEqual(result["year"], 2019)

        result = book_search.format_search_result(self.second_edition)
        self.assertEqual(result["title"], "Another Edition")
        self.assertEqual(result["key"], self.second_edition.remote_id)
        self.assertIsNone(result["year"])

    def test_search_result(self):
        """a class that stores info about a search result"""
        models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
            isbn_search_url="https://example.com/isbn?q=",
        )

        class TestConnector(AbstractMinimalConnector):
            """nothing added here"""

            def format_search_result(self, search_result):
                return search_result

            def get_or_create_book(self, remote_id):
                pass

            def parse_search_data(self, data):
                return data

            def format_isbn_search_result(self, search_result):
                return search_result

            def parse_isbn_search_data(self, data):
                return data

        test_connector = TestConnector("example.com")
        result = book_search.SearchResult(
            title="Title",
            key="https://example.com/book/1",
            author="Author Name",
            year="1850",
            connector=test_connector,
        )
        # there's really not much to test here, it's just a dataclass
        self.assertEqual(result.confidence, 1)
        self.assertEqual(result.title, "Title")
