""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class LandingViews(TestCase):
    """pages you land on without really trying"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_home_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Home.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream"):
            result = view(request)
        self.assertEqual(result.status_code, 200)
        result.render()

        request.user = self.anonymous_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)
        result.render()

    def test_about_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.About.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_discover(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Discover.as_view()
        request = self.factory.get("")
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
