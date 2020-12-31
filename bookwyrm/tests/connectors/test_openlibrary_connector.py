''' testing book data connectors '''
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors.openlibrary import Connector
from bookwyrm.connectors.openlibrary import get_languages, get_description
from bookwyrm.connectors.openlibrary import pick_default_edition, \
        get_openlibrary_key
from bookwyrm.connectors.abstract_connector import SearchResult
from bookwyrm.connectors.abstract_connector import ConnectorException


class Openlibrary(TestCase):
    ''' test loading data from openlibrary.org '''
    def setUp(self):
        ''' creates the connector we'll use '''
        models.Connector.objects.create(
            identifier='openlibrary.org',
            name='OpenLibrary',
            connector_file='openlibrary',
            base_url='https://openlibrary.org',
            books_url='https://openlibrary.org',
            covers_url='https://covers.openlibrary.org',
            search_url='https://openlibrary.org/search?q=',
        )
        self.connector = Connector('openlibrary.org')

        work_file = pathlib.Path(__file__).parent.joinpath(
            '../data/ol_work.json')
        edition_file = pathlib.Path(__file__).parent.joinpath(
            '../data/ol_edition.json')
        edition_list_file = pathlib.Path(__file__).parent.joinpath(
            '../data/ol_edition_list.json')
        self.work_data = json.loads(work_file.read_bytes())
        self.edition_data = json.loads(edition_file.read_bytes())
        self.edition_list_data = json.loads(edition_list_file.read_bytes())


    def test_get_remote_id_from_data(self):
        ''' format the remote id from the data '''
        data = {'key': '/work/OL1234W'}
        result = self.connector.get_remote_id_from_data(data)
        self.assertEqual(result, 'https://openlibrary.org/work/OL1234W')
        # error handlding
        with self.assertRaises(ConnectorException):
            self.connector.get_remote_id_from_data({})


    def test_is_work_data(self):
        ''' detect if the loaded json is a work '''
        self.assertEqual(self.connector.is_work_data(self.work_data), True)
        self.assertEqual(self.connector.is_work_data(self.edition_data), False)


    @responses.activate
    def test_get_edition_from_work_data(self):
        ''' loads a list of editions '''
        data = {'key': '/work/OL1234W'}
        responses.add(
            responses.GET,
            'https://openlibrary.org/work/OL1234W/editions',
            json={'entries': []},
            status=200)
        with patch('bookwyrm.connectors.openlibrary.pick_default_edition') \
                as pick_edition:
            pick_edition.return_value = 'hi'
            result = self.connector.get_edition_from_work_data(data)
        self.assertEqual(result, 'hi')


    @responses.activate
    def test_get_work_from_edition_data(self):
        ''' loads a list of editions '''
        data = {'works': [{'key': '/work/OL1234W'}]}
        responses.add(
            responses.GET,
            'https://openlibrary.org/work/OL1234W',
            json={'hi': 'there'},
            status=200)
        result = self.connector.get_work_from_edition_data(data)
        self.assertEqual(result, {'hi': 'there'})


    def test_pick_default_edition(self):
        ''' detect if the loaded json is an edition '''
        edition = pick_default_edition(self.edition_list_data['entries'])
        self.assertEqual(edition['key'], '/books/OL9788823M')


    @responses.activate
    def test_get_authors_from_data(self):
        ''' find authors in data '''
        responses.add(
            responses.GET,
            'https://openlibrary.org/authors/OL382982A',
            json={'hi': 'there'},
            status=200)
        results = self.connector.get_authors_from_data(self.work_data)
        for result in results:
            self.assertIsInstance(result, models.Author)


    def test_format_search_result(self):
        ''' translate json from openlibrary into SearchResult '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ol_search.json')
        search_data = json.loads(datafile.read_bytes())
        results = self.connector.parse_search_data(search_data)
        self.assertIsInstance(results, list)

        result = self.connector.format_search_result(results[0])
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.title, 'This Is How You Lose the Time War')
        self.assertEqual(
            result.key, 'https://openlibrary.org/works/OL20639540W')
        self.assertEqual(result.author, 'Amal El-Mohtar, Max Gladstone')
        self.assertEqual(result.year, 2019)
        self.assertEqual(result.connector, self.connector)


    def test_get_description(self):
        ''' should do some cleanup on the description data '''
        description = get_description(self.work_data['description'])
        expected = 'First in the Old Kingdom/Abhorsen series.'
        self.assertEqual(description, expected)


    def test_get_languages(self):
        ''' looks up languages from a list '''
        languages = get_languages(self.edition_data['languages'])
        self.assertEqual(languages, ['English'])


    def test_get_ol_key(self):
        ''' extracts the uuid '''
        key = get_openlibrary_key('/books/OL27320736M')
        self.assertEqual(key, 'OL27320736M')
