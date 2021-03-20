""" getting and verifying signatures """
import time
from collections import namedtuple
from urllib.parse import urlsplit
import pathlib
from unittest.mock import patch

import json
import responses

import pytest

from django.test import TestCase, Client
from django.utils.http import http_date

from bookwyrm import models
from bookwyrm.activitypub import Follow
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import create_key_pair, make_signature, make_digest


def get_follow_activity(follower, followee):
    """ generates a test activity """
    return Follow(
        id="https://test.com/user/follow/id",
        actor=follower.remote_id,
        object=followee.remote_id,
    ).serialize()


KeyPair = namedtuple("KeyPair", ("private_key", "public_key"))
Sender = namedtuple("Sender", ("remote_id", "key_pair"))


class Signature(TestCase):
    """ signature test """

    def setUp(self):
        """ create users and test data """
        self.mouse = models.User.objects.create_user(
            "mouse@%s" % DOMAIN, "mouse@example.com", "", local=True, localname="mouse"
        )
        self.rat = models.User.objects.create_user(
            "rat@%s" % DOMAIN, "rat@example.com", "", local=True, localname="rat"
        )
        self.cat = models.User.objects.create_user(
            "cat@%s" % DOMAIN, "cat@example.com", "", local=True, localname="cat"
        )

        private_key, public_key = create_key_pair()

        self.fake_remote = Sender(
            "http://localhost/user/remote", KeyPair(private_key, public_key)
        )

        models.SiteSettings.objects.create()

    def send(self, signature, now, data, digest):
        """ test request """
        c = Client()
        return c.post(
            urlsplit(self.rat.inbox).path,
            data=data,
            content_type="application/json",
            **{
                "HTTP_DATE": now,
                "HTTP_SIGNATURE": signature,
                "HTTP_DIGEST": digest,
                "HTTP_CONTENT_TYPE": "application/activity+json; charset=utf-8",
                "HTTP_HOST": DOMAIN,
            }
        )

    def send_test_request(  # pylint: disable=too-many-arguments
        self, sender, signer=None, send_data=None, digest=None, date=None
    ):
        """ sends a follow request to the "rat" user """
        now = date or http_date()
        data = json.dumps(get_follow_activity(sender, self.rat))
        digest = digest or make_digest(data)
        signature = make_signature(signer or sender, self.rat.inbox, now, digest)
        with patch("bookwyrm.views.inbox.activity_task.delay"):
            with patch("bookwyrm.models.user.set_remote_server.delay"):
                return self.send(signature, now, send_data or data, digest)

    def test_correct_signature(self):
        """ this one should just work """
        response = self.send_test_request(sender=self.mouse)
        self.assertEqual(response.status_code, 200)

    def test_wrong_signature(self):
        """Messages must be signed by the right actor.
        (cat cannot sign messages on behalf of mouse)"""
        response = self.send_test_request(sender=self.mouse, signer=self.cat)
        self.assertEqual(response.status_code, 401)

    @responses.activate
    def test_remote_signer(self):
        """ signtures for remote users """
        datafile = pathlib.Path(__file__).parent.joinpath("data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.fake_remote.remote_id
        data["publicKey"]["publicKeyPem"] = self.fake_remote.key_pair.public_key
        del data["icon"]  # Avoid having to return an avatar.
        responses.add(responses.GET, self.fake_remote.remote_id, json=data, status=200)
        responses.add(
            responses.GET, "https://localhost/.well-known/nodeinfo", status=404
        )
        responses.add(
            responses.GET,
            "https://example.com/user/mouse/outbox?page=true",
            json={"orderedItems": []},
            status=200,
        )

        with patch("bookwyrm.models.user.get_remote_reviews.delay"):
            response = self.send_test_request(sender=self.fake_remote)
            self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_key_needs_refresh(self):
        """ an out of date key should be updated and the new key work """
        datafile = pathlib.Path(__file__).parent.joinpath("data/ap_user.json")
        data = json.loads(datafile.read_bytes())
        data["id"] = self.fake_remote.remote_id
        data["publicKey"]["publicKeyPem"] = self.fake_remote.key_pair.public_key
        del data["icon"]  # Avoid having to return an avatar.
        responses.add(responses.GET, self.fake_remote.remote_id, json=data, status=200)
        responses.add(
            responses.GET, "https://localhost/.well-known/nodeinfo", status=404
        )

        # Second and subsequent fetches get a different key:
        key_pair = KeyPair(*create_key_pair())
        new_sender = Sender(self.fake_remote.remote_id, key_pair)
        data["publicKey"]["publicKeyPem"] = key_pair.public_key
        responses.add(responses.GET, self.fake_remote.remote_id, json=data, status=200)

        with patch("bookwyrm.models.user.get_remote_reviews.delay"):
            # Key correct:
            response = self.send_test_request(sender=self.fake_remote)
            self.assertEqual(response.status_code, 200)

            # Old key is cached, so still works:
            response = self.send_test_request(sender=self.fake_remote)
            self.assertEqual(response.status_code, 200)

            # Try with new key:
            response = self.send_test_request(sender=new_sender)
            self.assertEqual(response.status_code, 200)

            # Now the old key will fail:
            response = self.send_test_request(sender=self.fake_remote)
            self.assertEqual(response.status_code, 401)

    @responses.activate
    def test_nonexistent_signer(self):
        """ fail when unable to look up signer """
        responses.add(
            responses.GET,
            self.fake_remote.remote_id,
            json={"error": "not found"},
            status=404,
        )

        response = self.send_test_request(sender=self.fake_remote)
        self.assertEqual(response.status_code, 401)

    @pytest.mark.integration
    def test_changed_data(self):
        """Message data must match the digest header."""
        with patch("bookwyrm.activitypub.resolve_remote_id"):
            response = self.send_test_request(
                self.mouse, send_data=get_follow_activity(self.mouse, self.cat)
            )
            self.assertEqual(response.status_code, 401)

    @pytest.mark.integration
    def test_invalid_digest(self):
        """ signature digest must be valid """
        with patch("bookwyrm.activitypub.resolve_remote_id"):
            response = self.send_test_request(
                self.mouse, digest="SHA-256=AAAAAAAAAAAAAAAAAA"
            )
            self.assertEqual(response.status_code, 401)

    @pytest.mark.integration
    def test_old_message(self):
        """Old messages should be rejected to prevent replay attacks."""
        with patch("bookwyrm.activitypub.resolve_remote_id"):
            response = self.send_test_request(
                self.mouse, date=http_date(time.time() - 301)
            )
            self.assertEqual(response.status_code, 401)
