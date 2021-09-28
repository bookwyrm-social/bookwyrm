""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.settings import DOMAIN


# pylint: disable=too-many-public-methods
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class RegisterViews(TestCase):
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

        self.settings = models.SiteSettings.objects.create(
            id=1, require_confirm_email=False
        )

    def test_register(self, *_):
        """create a user"""
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            "register/",
            {
                "localname": "nutria-user.user_nutria",
                "password": "mouseword",
                "email": "aa@bb.cccc",
            },
        )
        with patch("bookwyrm.views.register.login"):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, "nutria-user.user_nutria@%s" % DOMAIN)
        self.assertEqual(nutria.localname, "nutria-user.user_nutria")
        self.assertEqual(nutria.local, True)

    @patch("bookwyrm.emailing.send_email.delay")
    def test_register_email_confirm(self, *_):
        """create a user"""
        self.settings.require_confirm_email = True
        self.settings.save()

        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            "register/",
            {
                "localname": "nutria",
                "password": "mouseword",
                "email": "aa@bb.cccc",
            },
        )
        with patch("bookwyrm.views.register.login"):
            response = view(request)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.get(localname="nutria")
        self.assertEqual(nutria.username, "nutria@%s" % DOMAIN)
        self.assertEqual(nutria.local, True)

        self.assertFalse(nutria.is_active)
        self.assertEqual(nutria.deactivation_reason, "pending")
        self.assertIsNotNone(nutria.confirmation_code)

    def test_register_trailing_space(self, *_):
        """django handles this so weirdly"""
        view = views.Register.as_view()
        request = self.factory.post(
            "register/",
            {"localname": "nutria ", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        with patch("bookwyrm.views.register.login"):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, "nutria@%s" % DOMAIN)
        self.assertEqual(nutria.localname, "nutria")
        self.assertEqual(nutria.local, True)

    def test_register_invalid_email(self, *_):
        """gotta have an email"""
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            "register/", {"localname": "nutria", "password": "mouseword", "email": "aa"}
        )
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        response.render()

    def test_register_invalid_username(self, *_):
        """gotta have an email"""
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            "register/",
            {"localname": "nut@ria", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        response.render()

        request = self.factory.post(
            "register/",
            {"localname": "nutr ia", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        response.render()

        request = self.factory.post(
            "register/",
            {"localname": "nut@ria", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        response.render()

    def test_register_closed_instance(self, *_):
        """you can't just register"""
        view = views.Register.as_view()
        self.settings.allow_registration = False
        self.settings.save()
        request = self.factory.post(
            "register/",
            {"localname": "nutria ", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_register_blocked_domain(self, *_):
        """you can't register with a blocked domain"""
        view = views.Register.as_view()
        models.EmailBlocklist.objects.create(domain="gmail.com")

        # one that fails
        request = self.factory.post(
            "register/",
            {"localname": "nutria ", "password": "mouseword", "email": "aa@gmail.com"},
        )
        result = view(request)
        self.assertEqual(result.status_code, 302)
        self.assertFalse(models.User.objects.filter(email="aa@gmail.com").exists())

        # one that succeeds
        request = self.factory.post(
            "register/",
            {"localname": "nutria ", "password": "mouseword", "email": "aa@bleep.com"},
        )
        with patch("bookwyrm.views.register.login"):
            result = view(request)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(models.User.objects.filter(email="aa@bleep.com").exists())

    def test_register_invite(self, *_):
        """you can't just register"""
        view = views.Register.as_view()
        self.settings.allow_registration = False
        self.settings.save()
        models.SiteInvite.objects.create(
            code="testcode", user=self.local_user, use_limit=1
        )
        self.assertEqual(models.SiteInvite.objects.get().times_used, 0)

        request = self.factory.post(
            "register/",
            {
                "localname": "nutria",
                "password": "mouseword",
                "email": "aa@bb.ccc",
                "invite_code": "testcode",
            },
        )
        with patch("bookwyrm.views.register.login"):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.SiteInvite.objects.get().times_used, 1)

        # invite already used to max capacity
        request = self.factory.post(
            "register/",
            {
                "localname": "nutria2",
                "password": "mouseword",
                "email": "aa@bb.ccc",
                "invite_code": "testcode",
            },
        )
        with self.assertRaises(PermissionDenied):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)

        # bad invite code
        request = self.factory.post(
            "register/",
            {
                "localname": "nutria3",
                "password": "mouseword",
                "email": "aa@bb.ccc",
                "invite_code": "dkfkdjgdfkjgkdfj",
            },
        )
        with self.assertRaises(Http404):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)

    def test_confirm_email_code_get(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        self.settings.require_confirm_email = True
        self.settings.save()

        self.local_user.is_active = False
        self.local_user.deactivation_reason = "pending"
        self.local_user.confirmation_code = "12345"
        self.local_user.save(
            broadcast=False,
            update_fields=["is_active", "deactivation_reason", "confirmation_code"],
        )
        view = views.ConfirmEmailCode.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, "12345")
        self.assertEqual(result.url, "/login/confirmed")
        self.assertEqual(result.status_code, 302)

        self.local_user.refresh_from_db()
        self.assertTrue(self.local_user.is_active)
        self.assertIsNone(self.local_user.deactivation_reason)

        request.user = self.local_user
        result = view(request, "12345")
        self.assertEqual(result.url, "/")
        self.assertEqual(result.status_code, 302)

    def test_confirm_email_code_get_invalid_code(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        self.settings.require_confirm_email = True
        self.settings.save()

        self.local_user.is_active = False
        self.local_user.deactivation_reason = "pending"
        self.local_user.confirmation_code = "12345"
        self.local_user.save(
            broadcast=False,
            update_fields=["is_active", "deactivation_reason", "confirmation_code"],
        )
        view = views.ConfirmEmailCode.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, "abcde")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertFalse(self.local_user.is_active)
        self.assertEqual(self.local_user.deactivation_reason, "pending")

    def test_confirm_email_get(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        self.settings.require_confirm_email = True
        self.settings.save()

        login = views.ConfirmEmail.as_view()
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
