""" test for app action functionality """
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class PasswordViews(TestCase):
    """view user and edit profile"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "password",
                local=True,
                localname="mouse",
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create(id=1)

    def test_password_reset_request(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.PasswordResetRequest.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_password_reset_request_post(self):
        """send 'em an email"""
        request = self.factory.post("", {"email": "aa@bb.ccc"})
        request.user = self.anonymous_user
        view = views.PasswordResetRequest.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 200)
        validate_html(resp.render())

        request = self.factory.post("", {"email": "mouse@mouse.com"})
        request.user = self.anonymous_user
        with patch("bookwyrm.emailing.send_email.delay"):
            resp = view(request)
        validate_html(resp.render())

        self.assertEqual(models.PasswordReset.objects.get().user, self.local_user)

    def test_password_reset(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.get("")
        request.user = self.anonymous_user
        result = view(request, code.code)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_password_reset_nonexistant_code(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.PasswordReset.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with self.assertRaises(PermissionDenied):
            view(request, "beep")

    def test_password_reset_invalid_code(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(
            user=self.local_user, expiry=timezone.now() - timedelta(days=2)
        )
        request = self.factory.get("")
        request.user = self.anonymous_user
        with self.assertRaises(PermissionDenied):
            view(request, code.code)

    def test_password_reset_logged_in(self):
        """redirect logged in users"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, code.code)
        self.assertEqual(result.status_code, 302)

    def test_password_reset_post(self):
        """reset from code"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post(
            "", {"password": "longwordsecure", "confirm_password": "longwordsecure"}
        )
        with patch("bookwyrm.views.landing.password.login"):
            resp = view(request, code.code)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(models.PasswordReset.objects.exists())

    def test_password_reset_wrong_code(self):
        """reset from code"""
        view = views.PasswordReset.as_view()
        models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post(
            "", {"password": "longwordsecure", "confirm_password": "longwordsecure"}
        )
        resp = view(request, "jhgdkfjgdf")
        validate_html(resp.render())
        self.assertTrue(models.PasswordReset.objects.exists())

    def test_password_reset_mismatch(self):
        """reset from code"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post(
            "", {"password": "longwordsecure", "confirm_password": "hihi"}
        )
        resp = view(request, code.code)
        validate_html(resp.render())
        self.assertTrue(models.PasswordReset.objects.exists())

    def test_password_reset_invalid(self):
        """reset from code"""
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post("", {"password": "a", "confirm_password": "a"})
        resp = view(request, code.code)
        validate_html(resp.render())
        self.assertTrue(models.PasswordReset.objects.exists())
