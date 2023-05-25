""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


# pylint: disable=too-many-public-methods
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class LoginViews(TestCase):
    """login and password management"""

    # pylint: disable=invalid-name
    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@your.domain.here",
                "mouse@mouse.com",
                "password",
                local=True,
                localname="mouse",
                two_factor_auth=False,
            )
            self.rat = models.User.objects.create_user(
                "rat@your.domain.here",
                "rat@rat.com",
                "password",
                local=True,
                localname="rat",
            )
            self.badger = models.User.objects.create_user(
                "badger@your.domain.here",
                "badger@badger.com",
                "password",
                local=True,
                localname="badger",
                two_factor_auth=True,
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create(id=1, require_confirm_email=False)

    def test_login_get(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        login = views.Login.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = login(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request.user = self.local_user
        result = login(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_localname(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse@mouse.com"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_username(self, *_):
        """valid login where the user provides their user@domain.com username"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse@your.domain.here"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_email(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_invalid_credentials(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse"
        form.data["password"] = "password1"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.context_data["login_form"].non_field_errors,
            "Username or password are incorrect",
        )

    def test_login_post_no_2fa_set(self, *_):
        """test user with 2FA null value is redirected to 2FA prompt page"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "rat"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/2fa-prompt")
        self.assertEqual(result.status_code, 302)

    def test_login_post_with_2fa(self, *_):
        """test user with 2FA turned on is redirected to 2FA login page"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "badger"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user
        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session.save()

        with patch("bookwyrm.views.landing.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/2fa-check")
        self.assertEqual(result.status_code, 302)
