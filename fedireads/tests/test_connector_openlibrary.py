''' testing book data connectors '''
from dateutil import parser
from django.test import TestCase
import json
import pathlib
import pytz

from fedireads import models
from fedireads.connectors.openlibrary import Connector
from fedireads.connectors.openlibrary import get_languages, get_description
from fedireads.connectors.abstract_connector import SearchResult, get_date


class Openlibrary(TestCase):
    def setUp(self):
        models.Connector.objects.create(
            identifier='openlibrary.org',
            name='OpenLibrary',
            connector_file='openlibrary',
            base_url='https://openlibrary.org',
            books_url='https://openlibrary.org',
            covers_url='https://covers.openlibrary.org',
            search_url='https://openlibrary.org/search?q=',
            key_name='openlibrary_key',
        )
        self.connector = Connector('openlibrary.org')

        work_file = pathlib.Path(__file__).parent.joinpath(
            'data/ol_work.json')
        edition_file = pathlib.Path(__file__).parent.joinpath(
            'data/ol_edition.json')
        self.work_data = json.loads(work_file.read_bytes())
        self.edition_data = json.loads(edition_file.read_bytes())


    def test_format_search_result(self):
        ''' translate json from openlibrary into SearchResult '''
        datafile = pathlib.Path(__file__).parent.joinpath('data/ol_search.json')
        search_data = json.loads(datafile.read_bytes())
        results = self.connector.parse_search_data(search_data)
        self.assertIsInstance(results, list)

        result = self.connector.format_search_result(results[0])
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, 'This Is How You Lose the Time War')
        self.assertEqual(result.key, 'OL20639540W')
        self.assertEqual(result.author, 'Amal El-Mohtar, Max Gladstone')
        self.assertEqual(result.year, 2019)


    def test_get_description(self):
        description = get_description(self.work_data['description'])
        expected = 'First in the Old Kingdom/Abhorsen series.'
        self.assertEqual(description, expected)


    def test_get_date(self):
        date = get_date(self.work_data['first_publish_date'])
        expected = pytz.utc.localize(parser.parse('1995'))
        self.assertEqual(date, expected)


    def test_get_languages(self):
        languages = get_languages(self.edition_data['languages'])
        self.assertEqual(languages, ['English'])
