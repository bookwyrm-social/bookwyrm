''' test for app action functionality '''
from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class LandingViews(TestCase):
    ''' pages you land on without really trying '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.mouse', 'password',
            local=True, localname='mouse')
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
        )


    def test_home_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Home.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        result = view(request)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.template_name, 'feed.html')

        request.user = self.anonymous_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.template_name, 'discover.html')


    def test_about_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.About.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'about.html')
        self.assertEqual(result.status_code, 200)


    def test_feed(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Feed.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        result = view(request, 'local')
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'feed.html')
        self.assertEqual(result.status_code, 200)


    def test_discover(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Discover.as_view()
        request = self.factory.get('')
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'discover.html')
        self.assertEqual(result.status_code, 200)


    def test_get_suggested_book(self):
        ''' gets books the ~*~ algorithm ~*~ thinks you want to post about '''
        models.ShelfBook.objects.create(
            book=self.book,
            added_by=self.local_user,
            shelf=self.local_user.shelf_set.get(identifier='reading')
        )
        suggestions = views.landing.get_suggested_books(self.local_user)
        self.assertEqual(suggestions[0]['name'], 'Currently Reading')
        self.assertEqual(suggestions[0]['books'][0], self.book)
