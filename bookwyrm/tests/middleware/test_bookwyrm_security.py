"""test security middleware"""

from collections import namedtuple
import json
import pathlib
import responses

from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils.http import http_date

from bookwyrm import models
from bookwyrm.activitypub.base_activity import get_representative
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import make_signature, create_key_pair


class TestBookWyrmSecurityChecks(TestCase):
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
        cls.site.require_login_everywhere = False
        cls.site.block_incoming_search = False
        cls.site.save(
            update_fields=["block_incoming_search", "require_login_everywhere"]
        )

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    def test_require_login_everywhere(self):
        """block pages with require_login_everywhere turned on"""

        self.client.user = AnonymousUser()

        # default is to allow user pages
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        # turn on require_login_everywhere
        self.site.require_login_everywhere = True
        self.site.save(update_fields=["require_login_everywhere"])

        # should redirect to login for user page
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/?next=/user/mouse")

    @override_settings(MIDDLEWARE=["bookwyrm.middleware.BookWyrmSecurityChecks"])
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
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    def test_require_login_everywhere_logged_in(self):
        """allow logged in users"""

        # turn on require_login_everywhere
        self.site.require_login_everywhere = True
        self.site.save(update_fields=["require_login_everywhere"])

        self.client.user = self.user
        self.client.login(username=self.user.username, password="changeme")
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/discover")
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    def test_require_login_everywhere_api_request(self):
        """allow api requests"""

        self.client.user = AnonymousUser()

        # default is to allow user pages
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        # turn on require_login_everywhere
        self.site.require_login_everywhere = True
        self.site.save(update_fields=["require_login_everywhere"])

        # allow API requewsts
        response = self.client.get(
            "/user/mouse",
            headers={
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
            },
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(MIDDLEWARE=["bookwyrm.middleware.BookWyrmSecurityChecks"])
    def test_block_incoming_search(self):
        """disallow search endpoint"""

        response = self.client.get("/search.json/?q=beep")
        self.assertEqual(response.status_code, 200)

        self.site.block_incoming_search = True
        self.site.save(update_fields=["block_incoming_search"])

        response = self.client.get("/search.json/?q=boop")
        self.assertEqual(response.status_code, 403)


class TestBookWyrmGetSignatures(TestCase):
    """aka authorized fetch"""

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
        cls.sender = get_representative()
        cls.sender.remote_id = "https://example.com/user/bookwyrm.instance.actor"
        key_pair = cls.sender.key_pair
        key_pair.remote_id = (
            "https://example.com/user/bookwyrm.instance.actor/#main-key"
        )
        key_pair.save(update_fields=["remote_id"])
        cls.sender.save(update_fields=["remote_id"])

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    def test_get_signature_not_required(self):
        """do not require signed GET activitypub requests"""

        now = http_date()
        self.client.user = AnonymousUser()
        response = self.client.get(
            "/user/mouse",
            headers={
                "Host": DOMAIN,
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
                "Date": now,
                "Signature": make_signature(
                    "get", self.sender, self.user.remote_id, now
                ),
            },
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    @responses.activate
    def test_get_signature_required(self):
        """require signed GET activitypub requests"""

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.sender.remote_id
        data["publicKey"]["id"] = f"{self.sender.remote_id}/#main-key"
        data["publicKey"]["publicKeyPem"] = self.sender.key_pair.public_key
        del data["icon"]  # Avoid having to return an avatar.

        responses.add(
            responses.GET, f"{self.sender.remote_id}/#main-key", json=data, status=200
        )
        responses.add(responses.GET, self.sender.remote_id, json=data, status=200)

        self.site.require_signed_get = True
        self.site.save(update_fields=["require_signed_get"])

        now = http_date()
        self.client.user = AnonymousUser()
        response = self.client.get(
            "/user/mouse",
            headers={
                "Host": DOMAIN,
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
                "Date": now,
                "Signature": make_signature(
                    "get", self.sender, self.user.remote_id, now
                ),
            },
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    @responses.activate
    def test_get_signature_required_wrong_signature(self):
        """require signed GET activitypub requests"""

        KeyPair = namedtuple("KeyPair", ("private_key", "public_key"))
        Sender = namedtuple("Sender", ("remote_id", "key_pair"))
        private_key, public_key = create_key_pair()
        self.unknown_sender = Sender(
            "http://localhost/user/remote", KeyPair(private_key, public_key)
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.unknown_sender.remote_id
        data["publicKey"]["id"] = f"{self.unknown_sender.remote_id}/#main-key"
        data["publicKey"]["publicKeyPem"] = self.sender.key_pair.public_key  # wrong key
        del data["icon"]  # Avoid having to return an avatar.

        responses.add(
            responses.GET,
            f"{self.unknown_sender.remote_id}/#main-key",
            json=data,
            status=200,
        )
        responses.add(
            responses.GET, self.unknown_sender.remote_id, json=data, status=200
        )

        self.site.require_signed_get = True
        self.site.save(update_fields=["require_signed_get"])

        now = http_date()
        self.client.user = AnonymousUser()
        response = self.client.get(
            "/user/mouse",
            headers={
                "Host": DOMAIN,
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
                "Date": now,
                "Signature": make_signature(
                    "get", self.unknown_sender, self.user.remote_id, now
                ),
            },
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    @responses.activate
    def test_get_signature_required_unknown_sender(self):
        """require signed GET activitypub requests"""

        KeyPair = namedtuple("KeyPair", ("private_key", "public_key"))
        Sender = namedtuple("Sender", ("remote_id", "key_pair"))
        private_key, public_key = create_key_pair()
        self.unknown_sender = Sender(
            "http://localhost/user/remote", KeyPair(private_key, public_key)
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.unknown_sender.remote_id
        data["publicKey"]["id"] = f"{self.unknown_sender.remote_id}/#main-key"
        data["publicKey"]["publicKeyPem"] = self.unknown_sender.key_pair.public_key
        del data["icon"]  # Avoid having to return an avatar.

        responses.add(
            responses.GET,
            f"{self.unknown_sender.remote_id}/#main-key",
            json=data,
            status=200,
        )
        responses.add(
            responses.GET, self.unknown_sender.remote_id, json=data, status=200
        )

        self.site.require_signed_get = True
        self.site.save(update_fields=["require_signed_get"])

        now = http_date()
        self.client.user = AnonymousUser()
        response = self.client.get(
            "/user/mouse",
            headers={
                "Host": DOMAIN,
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
                "Date": now,
                "Signature": make_signature(
                    "get", self.unknown_sender, self.user.remote_id, now
                ),
            },
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "bookwyrm.middleware.BookWyrmSecurityChecks",
        ]
    )
    @responses.activate
    def test_require_login_everywhere_and_signed_get_api_request(self):
        """allow api requests but only if signed"""

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.sender.remote_id
        data["publicKey"]["id"] = f"{self.sender.remote_id}/#main-key"
        data["publicKey"]["publicKeyPem"] = self.sender.key_pair.public_key
        del data["icon"]  # Avoid having to return an avatar.

        responses.add(
            responses.GET, f"{self.sender.remote_id}/#main-key", json=data, status=200
        )
        responses.add(responses.GET, self.sender.remote_id, json=data, status=200)

        self.site.require_signed_get = True
        self.site.require_login_everywhere = True
        self.site.save(update_fields=["require_signed_get", "require_login_everywhere"])

        # no signed headers, go away
        response = self.client.get("/user/mouse")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/?next=/user/mouse")

        now = http_date()
        self.client.user = AnonymousUser()
        response = self.client.get(
            "/user/mouse",
            headers={
                "Host": DOMAIN,
                "Accept": 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
                "Date": now,
                "Signature": make_signature(
                    "get", self.sender, self.user.remote_id, now
                ),
            },
        )
        # ok!
        self.assertEqual(response.status_code, 200)
