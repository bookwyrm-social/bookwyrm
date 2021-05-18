""" testing book data connectors """
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors import abstract_connector
from bookwyrm.connectors.abstract_connector import Mapping, SearchResult


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
            isbn_search_url="https://example.com/isbn?q=",
        )

        class TestConnector(abstract_connector.AbstractMinimalConnector):
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

        self.test_connector = TestConnector("example.com")

    def test_abstract_minimal_connector_init(self):
        """barebones connector for search with defaults"""
        connector = self.test_connector
        self.assertEqual(connector.connector, self.connector_info)
        self.assertEqual(connector.base_url, "https://example.com")
        self.assertEqual(connector.books_url, "https://example.com/books")
        self.assertEqual(connector.covers_url, "https://example.com/covers")
        self.assertEqual(connector.search_url, "https://example.com/search?q=")
        self.assertEqual(connector.isbn_search_url, "https://example.com/isbn?q=")
        self.assertIsNone(connector.name)
        self.assertEqual(connector.identifier, "example.com")
        self.assertFalse(connector.local)

    @responses.activate
    def test_search(self):
        """makes an http request to the outside service"""
        responses.add(
            responses.GET,
            "https://example.com/search?q=a%20book%20title",
            json=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"],
            status=200,
        )
        results = self.test_connector.search("a book title")
        self.assertEqual(len(results), 10)
        self.assertEqual(results[0], "a")
        self.assertEqual(results[1], "b")
        self.assertEqual(results[2], "c")

    @responses.activate
    def test_search_min_confidence(self):
        """makes an http request to the outside service"""
        responses.add(
            responses.GET,
            "https://example.com/search?q=a%20book%20title&min_confidence=1",
            json=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"],
            status=200,
        )
        results = self.test_connector.search("a book title", min_confidence=1)
        self.assertEqual(len(results), 10)

    @responses.activate
    def test_isbn_search(self):
        """makes an http request to the outside service"""
        responses.add(
            responses.GET,
            "https://example.com/isbn?q=123456",
            json=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"],
            status=200,
        )
        results = self.test_connector.isbn_search("123456")
        self.assertEqual(len(results), 10)

    def test_search_result(self):
        """a class that stores info about a search result"""
        result = SearchResult(
            title="Title",
            key="https://example.com/book/1",
            author="Author Name",
            year="1850",
            connector=self.test_connector,
        )
        # there's really not much to test here, it's just a dataclass
        self.assertEqual(result.confidence, 1)
        self.assertEqual(result.title, "Title")

    def test_create_mapping(self):
        """maps remote fields for book data to bookwyrm activitypub fields"""
        mapping = Mapping("isbn")
        self.assertEqual(mapping.local_field, "isbn")
        self.assertEqual(mapping.remote_field, "isbn")
        self.assertEqual(mapping.formatter("bb"), "bb")

    def test_create_mapping_with_remote(self):
        """the remote field is different than the local field"""
        mapping = Mapping("isbn", remote_field="isbn13")
        self.assertEqual(mapping.local_field, "isbn")
        self.assertEqual(mapping.remote_field, "isbn13")
        self.assertEqual(mapping.formatter("bb"), "bb")

    def test_create_mapping_with_formatter(self):
        """a function is provided to modify the data"""
        formatter = lambda x: "aa" + x
        mapping = Mapping("isbn", formatter=formatter)
        self.assertEqual(mapping.local_field, "isbn")
        self.assertEqual(mapping.remote_field, "isbn")
        self.assertEqual(mapping.formatter, formatter)
        self.assertEqual(mapping.formatter("bb"), "aabb")
