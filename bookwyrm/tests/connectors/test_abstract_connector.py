''' testing book data connectors '''
from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors.abstract_connector import Mapping
from bookwyrm.connectors.openlibrary import Connector


class AbstractConnector(TestCase):
    def setUp(self):
        self.book = models.Edition.objects.create(title='Example Edition')

        models.Connector.objects.create(
            identifier='example.com',
            connector_file='openlibrary',
            base_url='https://example.com',
            books_url='https:/example.com',
            covers_url='https://example.com',
            search_url='https://example.com/search?q=',
        )
        self.connector = Connector('example.com')

        self.data = {
            'title': 'Unused title',
            'ASIN': 'A00BLAH',
            'isbn_10': '1234567890',
            'isbn_13': 'blahhh',
            'blah': 'bip',
            'format': 'hardcover',
            'series': ['one', 'two'],
        }
        self.connector.key_mappings = [
            Mapping('isbn_10'),
            Mapping('isbn_13'),
            Mapping('lccn'),
            Mapping('asin'),
        ]


    def test_create_mapping(self):
        mapping = Mapping('isbn')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_remote(self):
        mapping = Mapping('isbn', remote_field='isbn13')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn13')
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_formatter(self):
        formatter = lambda x: 'aa' + x
        mapping = Mapping('isbn', formatter=formatter)
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.formatter, formatter)
        self.assertEqual(mapping.formatter('bb'), 'aabb')
