""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


# pylint: disable=too-many-public-methods
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class LoginViews(TestCase):
    """login and password management"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@your.domain.here",
                "mouse@mouse.com",
                "password",
                local=True,
                localname="mouse",
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
        result.render()
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

        with patch("bookwyrm.views.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_username(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse@your.domain.here"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.login.login"):
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

        with patch("bookwyrm.views.login.login"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_login_post_invalid_credentials(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Login.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse"
        form.data["password"] = "passsword1"
        request = self.factory.post("", form.data)
        request.user = self.anonymous_user

        with patch("bookwyrm.views.login.login"):
            result = view(request)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.context_data["login_form"].non_field_errors,
            "Username or password are incorrect",
        )
