""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class GetStartedViews(TestCase):
    """ helping new users get oriented """

    def setUp(self):
        """ we need basic test data and mocks """
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        self.book = models.Edition.objects.create(
            parent_work=models.Work.objects.create(title="hi"),
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.SiteSettings.objects.create()

    def test_profile_view(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.GetStartedProfile.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_profile_view_post(self):
        """ save basic user details """

    def test_books_view(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.GetStartedBooks.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_users_view(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.GetStartedUsers.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
