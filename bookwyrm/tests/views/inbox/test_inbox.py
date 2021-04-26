""" tests incoming activities"""
import json
import pathlib
from unittest.mock import patch

from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.test import TestCase, Client
from django.test.client import RequestFactory

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class Inbox(TestCase):
    """readthrough tests"""

    def setUp(self):
        """basic user and book data"""
        self.client = Client()
        self.factory = RequestFactory()
        local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        local_user.remote_id = "https://example.com/user/mouse"
        local_user.save(broadcast=False)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    def test_inbox_invalid_get(self):
        """shouldn't try to handle if the user is not found"""
        result = self.client.get("/inbox", content_type="application/json")
        self.assertIsInstance(result, HttpResponseNotAllowed)

    def test_inbox_invalid_user(self):
        """shouldn't try to handle if the user is not found"""
        result = self.client.post(
            "/user/bleh/inbox",
            '{"type": "Test", "object": "exists"}',
            content_type="application/json",
        )
        self.assertIsInstance(result, HttpResponseNotFound)

    def test_inbox_invalid_bad_signature(self):
        """bad request for invalid signature"""
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                "/user/mouse/inbox",
                '{"type": "Announce", "object": "exists"}',
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 401)

    def test_inbox_invalid_bad_signature_delete(self):
        """invalid signature for Delete is okay though"""
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                "/user/mouse/inbox",
                '{"type": "Delete", "object": "exists"}',
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)

    def test_inbox_unknown_type(self):
        """never heard of that activity type, don't have a handler for it"""
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            result = self.client.post(
                "/inbox",
                '{"type": "Fish", "object": "exists"}',
                content_type="application/json",
            )
            mock_valid.return_value = True
            self.assertIsInstance(result, HttpResponseNotFound)

    def test_inbox_success(self):
        """a known type, for which we start a task"""
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/list/22",
            "type": "BookList",
            "totalItems": 1,
            "first": "https://example.com/list/22?page=1",
            "last": "https://example.com/list/22?page=1",
            "name": "Test List",
            "owner": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "summary": "summary text",
            "curation": "curated",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = True

            with patch("bookwyrm.views.inbox.activity_task.delay"):
                result = self.client.post(
                    "/inbox", json.dumps(activity), content_type="application/json"
                )
        self.assertEqual(result.status_code, 200)

    def test_is_blocked_user_agent(self):
        """check for blocked servers"""
        request = self.factory.post(
            "",
            HTTP_USER_AGENT="http.rb/4.4.1 (Mastodon/3.3.0; +https://mastodon.social/)",
        )
        self.assertFalse(views.inbox.is_blocked_user_agent(request))

        models.FederatedServer.objects.create(
            server_name="mastodon.social", status="blocked"
        )
        self.assertTrue(views.inbox.is_blocked_user_agent(request))

    def test_is_blocked_activity(self):
        """check for blocked servers"""
        activity = {"actor": "https://mastodon.social/user/whaatever/else"}
        self.assertFalse(views.inbox.is_blocked_activity(activity))

        models.FederatedServer.objects.create(
            server_name="mastodon.social", status="blocked"
        )
        self.assertTrue(views.inbox.is_blocked_activity(activity))

    def test_create_by_deactivated_user(self):
        """don't let deactivated users post"""
        self.remote_user.delete(broadcast=False)
        self.assertTrue(self.remote_user.deleted)
        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        activity = self.create_json
        activity["actor"] = self.remote_user.remote_id
        activity["object"] = status_data

        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = True

            result = self.client.post(
                "/inbox", json.dumps(activity), content_type="application/json"
            )
        self.assertEqual(result.status_code, 403)
