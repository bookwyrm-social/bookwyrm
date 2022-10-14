""" test for app two factor auth functionality """
from unittest.mock import patch
import time
import pyotp

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views

# pylint: disable=too-many-public-methods
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class TwoFactorViews(TestCase):
    """Two Factor Authentication management"""

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
                two_factor_auth=True,
                otp_secret="UEWMVJHO23G5XLMVSOCL6TNTSSACJH2X",
                hotp_secret="DRMNMOU7ZRKH5YPW7PADOEYUF7MRIH46",
                hotp_count=0,
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_get_edit_2fa(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Edit2FA.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_get_edit_2fa_logged_out(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Edit2FA.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        result = view(request)
        self.assertEqual(result.status_code, 302)

    def test_post_edit_2fa(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Edit2FA.as_view()
        form = forms.ConfirmPasswordForm()
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.views.preferences.two_factor_auth.Edit2FA"):
            result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_post_confirm_2fa(self, *_):
        """check 2FA login works"""
        view = views.Confirm2FA.as_view()
        form = forms.Confirm2FAForm()
        totp = pyotp.TOTP("UEWMVJHO23G5XLMVSOCL6TNTSSACJH2X")
        form.data["otp"] = totp.now()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.views.preferences.two_factor_auth.Confirm2FA"):
            result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_get_disable_2fa(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Disable2FA.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_post_disable_2fa(self, *_):
        """check 2FA login works"""
        view = views.Disable2FA.as_view()
        request = self.factory.post("")
        request.user = self.local_user

        with patch("bookwyrm.views.preferences.two_factor_auth.Disable2FA"):
            result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_get_login_with_2fa(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.LoginWith2FA.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_post_login_with_2fa(self, *_):
        """check 2FA login works"""
        view = views.LoginWith2FA.as_view()
        form = forms.Confirm2FAForm()
        totp = pyotp.TOTP("UEWMVJHO23G5XLMVSOCL6TNTSSACJH2X")

        form.data["otp"] = totp.now()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session["2fa_auth_time"] = time.time()
        request.session["2fa_user"] = self.local_user.username
        request.session.save()

        with patch("bookwyrm.views.preferences.two_factor_auth.LoginWith2FA"), patch(
            "bookwyrm.views.preferences.two_factor_auth.login"
        ):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(request.user.is_authenticated)

    def test_post_login_with_2fa_wrong_code(self, *_):
        """check 2FA login fails"""
        view = views.LoginWith2FA.as_view()
        form = forms.Confirm2FAForm()
        form.data["otp"] = "111111"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session["2fa_auth_time"] = time.time()
        request.session["2fa_user"] = self.local_user.username
        request.session.save()

        with patch("bookwyrm.views.preferences.two_factor_auth.LoginWith2FA"):
            result = view(request)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.context_data["form"]["otp"].errors[0],
            "Incorrect code",
        )

    def test_post_login_with_2fa_expired(self, *_):
        """check 2FA login fails"""
        view = views.LoginWith2FA.as_view()
        form = forms.Confirm2FAForm()
        totp = pyotp.TOTP("UEWMVJHO23G5XLMVSOCL6TNTSSACJH2X")

        form.data["otp"] = totp.now()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session["2fa_user"] = self.local_user.username
        request.session["2fa_auth_time"] = "1663977030"

        with patch("bookwyrm.views.preferences.two_factor_auth.LoginWith2FA"):
            result = view(request)
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_get_generate_backup_codes(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GenerateBackupCodes.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)

    def test_get_prompt_2fa(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Prompt2FA.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.status_code, 200)
