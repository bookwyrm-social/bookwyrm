""" test for app action functionality """
from unittest.mock import patch

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class ChangePasswordViews(TestCase):
    """view user and edit profile"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "password",
                local=True,
                localname="mouse",
            )
        models.SiteSettings.objects.create(id=1)

    def test_password_change_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ChangePassword.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_password_change(self):
        """change password"""
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post("", {"password": "hi", "confirm-password": "hi"})
        request.user = self.local_user
        with patch("bookwyrm.views.preferences.change_password.login"):
            view(request)
        self.assertNotEqual(self.local_user.password, password_hash)

    def test_password_change_mismatch(self):
        """change password"""
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post("", {"password": "hi", "confirm-password": "hihi"})
        request.user = self.local_user
        view(request)
        self.assertEqual(self.local_user.password, password_hash)
