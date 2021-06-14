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
class AuthenticationViews(TestCase):
    """login and password management"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "password",
            local=True,
            localname="mouse",
        )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        self.settings = models.SiteSettings.objects.create(id=1)

    def test_login_get(self):
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

    def test_register(self):
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
        with patch("bookwyrm.views.authentication.login"):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, "nutria-user.user_nutria@%s" % DOMAIN)
        self.assertEqual(nutria.localname, "nutria-user.user_nutria")
        self.assertEqual(nutria.local, True)

    def test_register_trailing_space(self):
        """django handles this so weirdly"""
        view = views.Register.as_view()
        request = self.factory.post(
            "register/",
            {"localname": "nutria ", "password": "mouseword", "email": "aa@bb.ccc"},
        )
        with patch("bookwyrm.views.authentication.login"):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, "nutria@%s" % DOMAIN)
        self.assertEqual(nutria.localname, "nutria")
        self.assertEqual(nutria.local, True)

    def test_register_invalid_email(self):
        """gotta have an email"""
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            "register/", {"localname": "nutria", "password": "mouseword", "email": "aa"}
        )
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        response.render()

    def test_register_invalid_username(self):
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

    def test_register_closed_instance(self):
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

    def test_register_invite(self):
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
        with patch("bookwyrm.views.authentication.login"):
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
