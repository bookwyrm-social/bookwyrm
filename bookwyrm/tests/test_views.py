''' test for app action functionality '''
import json
from unittest.mock import patch

from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.connectors import abstract_connector
from bookwyrm.settings import DOMAIN


class Views(TestCase):
    ''' every response to a get request, html or json '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.book = models.Edition.objects.create(title='Test Book')
        models.Connector.objects.create(
            identifier='self',
            connector_file='self_connector',
            local=True
        )


    def test_search_json_response(self):
        ''' searches local data only and returns book data in json format '''
        # we need a connector for this, sorry
        request = self.factory.get('', {'q': 'Test Book'})
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = True
            response = views.search(request)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], 'Test Book')
        self.assertEqual(
            data[0]['key'], 'https://%s/book/%d' % (DOMAIN, self.book.id))


    def test_search_html_response(self):
        ''' searches remote connectors '''
        class TestConnector(abstract_connector.AbstractMinimalConnector):
            ''' nothing added here '''
            def format_search_result(self, search_result):
                pass
            def get_or_create_book(self, remote_id):
                pass
            def parse_search_data(self, data):
                pass
        models.Connector.objects.create(
            identifier='example.com',
            connector_file='openlibrary',
            base_url='https://example.com',
            books_url='https://example.com/books',
            covers_url='https://example.com/covers',
            search_url='https://example.com/search?q=',
        )
        connector = TestConnector('example.com')

        search_result = abstract_connector.SearchResult(
            key='http://www.example.com/book/1',
            title='Gideon the Ninth',
            author='Tamsyn Muir',
            year='2019',
            connector=connector
        )

        request = self.factory.get('', {'q': 'Test Book'})
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = False
            with patch('bookwyrm.books_manager.search') as manager:
                manager.return_value = [search_result]
                response = views.search(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.template_name, 'search_results.html')
        self.assertEqual(
            response.context_data['book_results'][0].title, 'Gideon the Ninth')
