""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html

# pylint: disable=unused-argument
class DirectoryViews(TestCase):
    """tag views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )

        models.SiteSettings.objects.create()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.suggested_users.rerank_user_task.delay")
    def test_directory_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
            discoverable=True,
        )
        view = views.Directory.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_directory_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Directory.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_directory_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Directory.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request)
        self.assertEqual(result.status_code, 302)
