''' testing book data connectors '''
from dateutil import parser
from django.test import TestCase
import json
import pathlib

from fedireads import models
from fedireads.connectors.fedireads_connector import Connector
from fedireads.connectors.abstract_connector import SearchResult, get_date


class FedireadsConnector(TestCase):
    def setUp(self):
        models.Connector.objects.create(
            identifier='example.com',
            connector_file='fedireads_connector',
            base_url='https://example.com',
            books_url='https://example.com',
            covers_url='https://example.com/images/covers',
            search_url='https://example.com/search?q=',
            key_name='remote_id',
        )
        self.connector = Connector('example.com')

        work_file = pathlib.Path(__file__).parent.joinpath(
            'data/fr_work.json')
        edition_file = pathlib.Path(__file__).parent.joinpath(
            'data/fr_edition.json')
        self.work_data = json.loads(work_file.read_bytes())
        self.edition_data = json.loads(edition_file.read_bytes())


    def test_is_work_data(self):
        self.assertEqual(self.connector.is_work_data(self.work_data), True)
        self.assertEqual(self.connector.is_work_data(self.edition_data), False)


    def test_get_edition_from_work_data(self):
        edition = self.connector.get_edition_from_work_data(self.work_data)
        self.assertEqual(edition['url'], 'https://example.com/book/122')


    def test_get_work_from_edition_data(self):
        work = self.connector.get_work_from_edition_date(self.edition_data)
        self.assertEqual(work['url'], 'https://example.com/book/121')


    def test_format_search_result(self):
        datafile = pathlib.Path(__file__).parent.joinpath('data/fr_search.json')
        search_data = json.loads(datafile.read_bytes())
        results = self.connector.parse_search_data(search_data)
        self.assertIsInstance(results, list)

        result = self.connector.format_search_result(results[0])
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, 'Jonathan Strange and Mr Norrell')
        self.assertEqual(result.key, 'https://example.com/book/122')
        self.assertEqual(result.author, 'Susanna Clarke')
        self.assertEqual(result.year, 2017)


    def test_get_date(self):
        date = get_date(self.edition_data['published_date'])
        expected = parser.parse("2017-05-10T00:00:00+00:00")
        self.assertEqual(date, expected)
