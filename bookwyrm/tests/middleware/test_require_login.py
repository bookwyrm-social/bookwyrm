"""test require login middleware"""

import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from bookwyrm import models
from bookwyrm.settings import DOMAIN


class TestRequireLogin(TestCase):
    """lets get fuzzing"""

    @classmethod
    def setUpTestData(cls):
        """create users and test data"""

        cls.user = models.User.objects.create_user(
            f"mouse@{DOMAIN}",
            "mouse@example.com",
            "changeme",
            local=True,
            localname="mouse",
        )

        cls.site = models.SiteSettings.get()
        cls.site.require_login_nearly_everywhere = False
        cls.site.block_incoming_search = False
        cls.site.save(
            update_fields=["block_incoming_search", "require_login_nearly_everywhere"]
        )

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.RequireLoginNearlyEverywhere",
        ]
    )
    def test_require_login_everywhere(self):
        """block pages with require_login_nearly_everywhere turned on"""

        self.client.user = AnonymousUser()

        # default is to allow user pages
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        # turn on require_login_nearly_everywhere
        self.site.require_login_nearly_everywhere = True
        self.site.save(update_fields=["require_login_nearly_everywhere"])

        # should redirect to login for user page
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/?next=/user/mouse")

        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_activity_stream"
        ) as mock:
            response = self.client.get("/discover")
            self.assertEqual(response.status_code, 302)

        response = self.client.get("")
        self.assertEqual(response.status_code, 200)

    @override_settings(MIDDLEWARE=["bookwyrm.middleware.RequireLoginNearlyEverywhere"])
    def test_require_login_everywhere_allowed_pages(self):
        """don't block allowlist"""

        # should allow allow_list pages
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/2fa-check")
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.RequireLoginNearlyEverywhere",
        ]
    )
    def test_require_login_everywhere_logged_in(self):
        """allow logged in users"""

        # turn on require_login_nearly_everywhere
        self.site.require_login_nearly_everywhere = True
        self.site.save(update_fields=["require_login_nearly_everywhere"])

        self.client.user = self.user
        self.client.login(username=self.user.username, password="changeme")

        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_activity_stream"
        ) as mock:
            response = self.client.get("/discover")
            self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.RequireLoginNearlyEverywhere",
        ]
    )
    def test_require_login_everywhere_api_request(self):
        """allow api requests"""

        self.client.user = AnonymousUser()

        # default is to allow user pages
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        # turn on require_login_nearly_everywhere
        self.site.require_login_nearly_everywhere = True
        self.site.save(update_fields=["require_login_nearly_everywhere"])

        # allow API requewsts
        response = self.client.get(
            "/user/mouse",
            headers={
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
            },
        )
        self.assertEqual(response.status_code, 200)
