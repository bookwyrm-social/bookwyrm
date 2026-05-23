"""test get signatures middleware"""

from collections import namedtuple
import json
import pathlib
import responses

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils.http import http_date

from bookwyrm import models
from bookwyrm.activitypub.base_activity import get_representative
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import make_signature, create_key_pair


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
            "bookwyrm.middleware.RequireSignedGet",
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
            "bookwyrm.middleware.RequireSignedGet",
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
            "bookwyrm.middleware.RequireSignedGet",
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
            "bookwyrm.middleware.RequireSignedGet",
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
            "bookwyrm.middleware.RequireSignedGet",
            "bookwyrm.middleware.RequireLoginNearlyEverywhere",
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
        self.site.require_login_nearly_everywhere = True
        self.site.save(
            update_fields=["require_signed_get", "require_login_nearly_everywhere"]
        )

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
