''' testing book data connectors '''
from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors.abstract_connector import Mapping, SearchResult
from bookwyrm.connectors.openlibrary import Connector


class AbstractConnector(TestCase):
    ''' generic code for connecting to outside data sources '''
    def setUp(self):
        ''' we need an example connector '''
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
        ''' maps remote fields for book data to bookwyrm activitypub fields '''
        mapping = Mapping('isbn')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_remote(self):
        ''' the remote field is different than the local field '''
        mapping = Mapping('isbn', remote_field='isbn13')
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn13')
        self.assertEqual(mapping.formatter('bb'), 'bb')


    def test_create_mapping_with_formatter(self):
        ''' a function is provided to modify the data '''
        formatter = lambda x: 'aa' + x
        mapping = Mapping('isbn', formatter=formatter)
        self.assertEqual(mapping.local_field, 'isbn')
        self.assertEqual(mapping.remote_field, 'isbn')
        self.assertEqual(mapping.formatter, formatter)
        self.assertEqual(mapping.formatter('bb'), 'aabb')


    def test_search_result(self):
        ''' a class that stores info about a search result '''
        result = SearchResult(
            title='Title',
            key='https://example.com/book/1',
            author='Author Name',
            year='1850',
            connector=self.connector,
        )
        # there's really not much to test here, it's just a dataclass
        self.assertEqual(result.confidence, 1)
        self.assertEqual(result.title, 'Title')
