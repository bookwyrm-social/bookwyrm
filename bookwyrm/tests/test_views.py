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
        self.work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Test Book', parent_work=self.work)
        models.Connector.objects.create(
            identifier='self',
            connector_file='self_connector',
            local=True
        )
        self.local_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'password', local=True)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )


    def test_get_user_from_username(self):
        ''' works for either localname or username '''
        self.assertEqual(
            views.get_user_from_username('mouse'), self.local_user)
        self.assertEqual(
            views.get_user_from_username('mouse@%s' % DOMAIN), self.local_user)
        with self.assertRaises(models.User.DoesNotExist):
            views.get_user_from_username('mojfse@example.com')


    def test_is_api_request(self):
        ''' should it return html or json '''
        request = self.factory.get('/path')
        request.headers = {'Accept': 'application/json'}
        self.assertTrue(views.is_api_request(request))

        request = self.factory.get('/path.json')
        request.headers = {'Accept': 'Praise'}
        self.assertTrue(views.is_api_request(request))

        request = self.factory.get('/path')
        request.headers = {'Accept': 'Praise'}
        self.assertFalse(views.is_api_request(request))


    def test_get_activity_feed(self):
        ''' loads statuses '''
        rat = models.User.objects.create_user(
            'rat', 'rat@rat.rat', 'password', local=True)

        public_status = models.Comment.objects.create(
            content='public status', book=self.book, user=self.local_user)
        direct_status = models.Status.objects.create(
            content='direct', user=self.local_user, privacy='direct')

        rat_public = models.Status.objects.create(
            content='blah blah', user=rat)
        rat_unlisted = models.Status.objects.create(
            content='blah blah', user=rat, privacy='unlisted')
        remote_status = models.Status.objects.create(
            content='blah blah', user=self.remote_user)
        followers_status = models.Status.objects.create(
            content='blah', user=rat, privacy='followers')
        rat_mention = models.Status.objects.create(
            content='blah blah blah', user=rat, privacy='followers')
        rat_mention.mention_users.set([self.local_user])

        statuses = views.get_activity_feed(self.local_user, 'home')
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[1], public_status)
        self.assertEqual(statuses[0], rat_mention)

        statuses = views.get_activity_feed(
            self.local_user, 'home', model=models.Comment)
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], public_status)

        statuses = views.get_activity_feed(self.local_user, 'local')
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[1], public_status)
        self.assertEqual(statuses[0], rat_public)

        statuses = views.get_activity_feed(self.local_user, 'direct')
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], direct_status)

        statuses = views.get_activity_feed(self.local_user, 'federated')
        self.assertEqual(len(statuses), 3)
        self.assertEqual(statuses[2], public_status)
        self.assertEqual(statuses[1], rat_public)
        self.assertEqual(statuses[0], remote_status)

        statuses = views.get_activity_feed(self.local_user, 'friends')
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[1], public_status)
        self.assertEqual(statuses[0], rat_mention)

        rat.followers.add(self.local_user)
        statuses = views.get_activity_feed(self.local_user, 'friends')
        self.assertEqual(len(statuses), 5)
        self.assertEqual(statuses[4], public_status)
        self.assertEqual(statuses[3], rat_public)
        self.assertEqual(statuses[2], rat_unlisted)
        self.assertEqual(statuses[1], followers_status)
        self.assertEqual(statuses[0], rat_mention)


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


    def test_editions_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = False
            result = views.editions_page(request, self.work.id)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'editions.html')
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = True
            result = views.editions_page(request, self.work.id)
        self.assertIsInstance(result, JsonResponse)
        self.assertEqual(result.status_code, 200)


    def test_author_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        author = models.Author.objects.create(name='Jessica')
        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = False
            result = views.author_page(request, author.id)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'author.html')
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = True
            result = views.author_page(request, author.id)
        self.assertIsInstance(result, JsonResponse)
        self.assertEqual(result.status_code, 200)


    def test_tag_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        tag = models.Tag.objects.create(name='hi there')
        models.UserTag.objects.create(
            tag=tag, user=self.local_user, book=self.book)
        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = False
            result = views.tag_page(request, tag.identifier)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'tag.html')
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('')
        with patch('bookwyrm.views.is_api_request') as is_api:
            is_api.return_value = True
            result = views.tag_page(request, tag.identifier)
        self.assertIsInstance(result, JsonResponse)
        self.assertEqual(result.status_code, 200)
