""" test for app action functionality """
from unittest.mock import patch

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class ChangePasswordViews(TestCase):
    """view user and edit profile"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "password",
                local=True,
                localname="mouse",
            )
        models.SiteSettings.objects.create(id=1)

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

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
        request = self.factory.post(
            "",
            {
                "current_password": "password",
                "password": "longwordsecure",
                "confirm_password": "longwordsecure",
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.views.preferences.change_password.login"):
            result = view(request)
        validate_html(result.render())
        self.local_user.refresh_from_db()
        self.assertNotEqual(self.local_user.password, password_hash)

    def test_password_change_wrong_current(self):
        """change password"""
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post(
            "",
            {
                "current_password": "not my password",
                "password": "longwordsecure",
                "confirm_password": "hihi",
            },
        )
        request.user = self.local_user
        result = view(request)
        validate_html(result.render())
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.password, password_hash)

    def test_password_change_mismatch(self):
        """change password"""
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post(
            "",
            {
                "current_password": "password",
                "password": "longwordsecure",
                "confirm_password": "hihi",
            },
        )
        request.user = self.local_user
        result = view(request)
        validate_html(result.render())
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.password, password_hash)

    def test_password_change_invalid(self):
        """change password"""
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post(
            "",
            {
                "current_password": "password",
                "password": "hi",
                "confirm_password": "hi",
            },
        )
        request.user = self.local_user
        result = view(request)
        validate_html(result.render())
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.password, password_hash)
