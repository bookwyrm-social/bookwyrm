''' test for app action functionality '''
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse


class ListViews(TestCase):
    ''' tag views'''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse',
            remote_id='https://example.com/users/mouse',
        )
        self.work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=self.work
        )
        self.list = models.List.objects.create(
            name='Test List', user=self.local_user)
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()


    def test_lists_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Lists.as_view()
        models.List.objects.create(name='Public list', user=self.local_user)
        models.List.objects.create(
            name='Private list', privacy='private', user=self.local_user)
        request = self.factory.get('')
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)


    def test_list_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.List.as_view()
        request = self.factory.get('')
        request.user = self.local_user

        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('/?page=1')
        request.user = self.local_user
        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)
