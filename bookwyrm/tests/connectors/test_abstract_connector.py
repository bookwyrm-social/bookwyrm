""" testing book data connectors """
from unittest.mock import patch
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors import abstract_connector
from bookwyrm.connectors.abstract_connector import Mapping
from bookwyrm.settings import DOMAIN


class AbstractConnector(TestCase):
    """generic code for connecting to outside data sources"""

    def setUp(self):
        """we need an example connector"""
        self.connector_info = models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
        )
        work_data = {
            "id": "abc1",
            "title": "Test work",
            "type": "work",
            "openlibraryKey": "OL1234W",
        }
        self.work_data = work_data
        edition_data = {
            "id": "abc2",
            "title": "Test edition",
            "type": "edition",
            "openlibraryKey": "OL1234M",
        }
        self.edition_data = edition_data

        class TestConnector(abstract_connector.AbstractConnector):
            """nothing added here"""

            def format_search_result(self, search_result):
                return search_result

            def parse_search_data(self, data):
                return data

            def format_isbn_search_result(self, search_result):
                return search_result

            def parse_isbn_search_data(self, data):
                return data

            def is_work_data(self, data):
                return data["type"] == "work"

            def get_edition_from_work_data(self, data):
                return edition_data

            def get_work_from_edition_data(self, data):
                return work_data

            def get_authors_from_data(self, data):
                return []

            def expand_book_data(self, book):
                pass

        self.connector = TestConnector("example.com")
        self.connector.book_mappings = [
            Mapping("id"),
            Mapping("title"),
            Mapping("openlibraryKey"),
        ]

        self.book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1234",
            openlibrary_key="OL1234M",
        )

    def test_abstract_connector_init(self):
        """barebones connector for search with defaults"""
        self.assertIsInstance(self.connector.book_mappings, list)

    def test_get_or_create_book_existing(self):
        """find an existing book by remote/origin id"""
        self.assertEqual(models.Book.objects.count(), 1)
        self.assertEqual(
            self.book.remote_id, "https://%s/book/%d" % (DOMAIN, self.book.id)
        )
        self.assertEqual(self.book.origin_id, "https://example.com/book/1234")

        # dedupe by origin id
        result = self.connector.get_or_create_book("https://example.com/book/1234")
        self.assertEqual(models.Book.objects.count(), 1)
        self.assertEqual(result, self.book)

        # dedupe by remote id
        result = self.connector.get_or_create_book(
            "https://%s/book/%d" % (DOMAIN, self.book.id)
        )
        self.assertEqual(models.Book.objects.count(), 1)
        self.assertEqual(result, self.book)

    @responses.activate
    def test_get_or_create_book_deduped(self):
        """load remote data and deduplicate"""
        responses.add(
            responses.GET, "https://example.com/book/abcd", json=self.edition_data
        )
        with patch("bookwyrm.connectors.abstract_connector.load_more_data.delay"):
            result = self.connector.get_or_create_book("https://example.com/book/abcd")
        self.assertEqual(result, self.book)
        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Edition.objects.count(), 1)

    @responses.activate
    def test_get_or_create_author(self):
        """load an author"""
        self.connector.author_mappings = [
            Mapping("id"),
            Mapping("name"),
        ]

        responses.add(
            responses.GET,
            "https://www.example.com/author",
            json={"id": "https://www.example.com/author", "name": "Test Author"},
        )
        result = self.connector.get_or_create_author("https://www.example.com/author")
        self.assertIsInstance(result, models.Author)
        self.assertEqual(result.name, "Test Author")
        self.assertEqual(result.origin_id, "https://www.example.com/author")

    def test_get_or_create_author_existing(self):
        """get an existing author"""
        author = models.Author.objects.create(name="Test Author")
        result = self.connector.get_or_create_author(author.remote_id)
        self.assertEqual(author, result)
