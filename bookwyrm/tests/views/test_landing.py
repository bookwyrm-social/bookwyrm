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
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
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

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    def test_home_page(self, _):
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

    def test_landing(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Landing.as_view()
        request = self.factory.get("")
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
