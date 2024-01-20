""" testing book data connectors """
from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors import abstract_connector
from bookwyrm.connectors.abstract_connector import Mapping


class AbstractConnector(TestCase):
    """generic code for connecting to outside data sources"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need an example connector in the database"""
        self.connector_info = models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
            isbn_search_url="https://example.com/isbn?q=",
        )

    def setUp(self):
        """instantiate example connector"""

        class TestConnector(abstract_connector.AbstractMinimalConnector):
            """nothing added here"""

            def get_or_create_book(self, remote_id):
                pass

            def parse_search_data(self, data, min_confidence):
                return data

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
