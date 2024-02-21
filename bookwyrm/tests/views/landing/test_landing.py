""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views
from bookwyrm.tests.validate_html import validate_html


class LandingViews(TestCase):
    """pages you land on without really trying"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    def test_home_page(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Home.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream"):
            result = view(request)
        self.assertEqual(result.status_code, 200)
        validate_html(result.render())

        request.user = self.anonymous_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)
        validate_html(result.render())

    def test_about_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.about
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_conduct_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.conduct
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_privacy_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.privacy
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_impressum_page_off(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.impressum
        request = self.factory.get("")
        request.user = self.local_user
        with self.assertRaises(Http404):
            view(request)

    def test_impressum_page_on(self):
        """there are so many views, this just makes sure it LOADS"""
        site = models.SiteSettings.objects.get()
        site.show_impressum = True
        site.save()

        view = views.impressum
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_landing(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Landing.as_view()
        request = self.factory.get("")
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
