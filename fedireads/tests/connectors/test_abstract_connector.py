''' testing book data connectors '''
from django.test import TestCase

from fedireads import models
from fedireads.connectors.abstract_connector import Mapping,\
        update_from_mappings
from fedireads.connectors.fedireads_connector import Connector


class FedireadsConnector(TestCase):
    def setUp(self):
        self.book = models.Edition.objects.create(title='Example Edition')

        models.Connector.objects.create(
            identifier='example.com',
            connector_file='fedireads_connector',
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
            Mapping('isbn_10', model=models.Edition),
            Mapping('isbn_13'),
            Mapping('lccn', model=models.Work),
            Mapping('asin', remote_field='ASIN'),
        ]


    def test_create_mapping(self):
        mapping = Mapping('isbn')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.model, None)
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_remote(self):
        mapping = Mapping('isbn', remote_field='isbn13')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn13')
        self.assertEqual(mapping.model, None)
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_formatter(self):
        formatter = lambda x: 'aa' + x
        mapping = Mapping('isbn', formatter=formatter)
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.formatter, formatter)
        self.assertEqual(mapping.model, None)
        self.assertEqual(mapping.formatter('bb'), 'aabb')


    def test_update_from_mappings(self):
        data = {
            'title': 'Unused title',
            'isbn_10': '1234567890',
            'isbn_13': 'blahhh',
            'blah': 'bip',
            'format': 'hardcover',
            'series': ['one', 'two'],
        }
        mappings = [
            Mapping('isbn_10'),
            Mapping('blah'),# not present on self.book
            Mapping('physical_format', remote_field='format'),
            Mapping('series', formatter=lambda x: x[0]),
        ]
        book = update_from_mappings(self.book, data, mappings)
        self.assertEqual(book.title, 'Example Edition')
        self.assertEqual(book.isbn_10, '1234567890')
        self.assertEqual(book.isbn_13, None)
        self.assertEqual(book.physical_format, 'hardcover')
        self.assertEqual(book.series, 'one')


    def test_match_from_mappings(self):
        edition = models.Edition.objects.create(
            title='Blah',
            isbn_13='blahhh',
        )
        match = self.connector.match_from_mappings(self.data, models.Edition)
        self.assertEqual(match, edition)


    def test_match_from_mappings_with_model(self):
        edition = models.Edition.objects.create(
            title='Blah',
            isbn_10='1234567890',
        )
        match = self.connector.match_from_mappings(self.data, models.Edition)
        self.assertEqual(match, edition)


    def test_match_from_mappings_with_remote(self):
        edition = models.Edition.objects.create(
            title='Blah',
            asin='A00BLAH',
        )
        match = self.connector.match_from_mappings(self.data, models.Edition)
        self.assertEqual(match, edition)


    def test_match_from_mappings_no_match(self):
        edition = models.Edition.objects.create(
            title='Blah',
        )
        match = self.connector.match_from_mappings(self.data, models.Edition)
        self.assertEqual(match, None)
