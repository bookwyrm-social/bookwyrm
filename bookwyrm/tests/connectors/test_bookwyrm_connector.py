''' testing book data connectors '''
import json
import pathlib
from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors.bookwyrm_connector import Connector
from bookwyrm.connectors.abstract_connector import SearchResult


class BookWyrmConnector(TestCase):
    ''' this connector doesn't do much, just search '''
    def setUp(self):
        ''' create the connector '''
        models.Connector.objects.create(
            identifier='example.com',
            connector_file='bookwyrm_connector',
            base_url='https://example.com',
            books_url='https://example.com',
            covers_url='https://example.com/images/covers',
            search_url='https://example.com/search?q=',
        )
        self.connector = Connector('example.com')

        work_file = pathlib.Path(__file__).parent.joinpath(
            '../data/fr_work.json')
        edition_file = pathlib.Path(__file__).parent.joinpath(
            '../data/fr_edition.json')
        self.work_data = json.loads(work_file.read_bytes())
        self.edition_data = json.loads(edition_file.read_bytes())


    def test_format_search_result(self):
        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/fr_search.json')
        search_data = json.loads(datafile.read_bytes())
        results = self.connector.parse_search_data(search_data)
        self.assertIsInstance(results, list)

        result = self.connector.format_search_result(results[0])
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, 'Jonathan Strange and Mr Norrell')
        self.assertEqual(result.key, 'https://example.com/book/122')
        self.assertEqual(result.author, 'Susanna Clarke')
        self.assertEqual(result.year, 2017)
