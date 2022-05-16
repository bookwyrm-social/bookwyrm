""" testing models """
import json
from unittest.mock import patch
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.settings import USE_HTTPS, DOMAIN

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
class User(TestCase):
    protocol = "https://" if USE_HTTPS else "http://"

    def setUp(self):
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
                f"mouse@{DOMAIN}",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
                name="hi",
                bookwyrm_user=False,
            )

    def test_computed_fields(self):
        """username instead of id here"""
        expected_id = f"{self.protocol}{DOMAIN}/user/mouse"
        self.assertEqual(self.user.remote_id, expected_id)
        self.assertEqual(self.user.username, f"mouse@{DOMAIN}")
        self.assertEqual(self.user.localname, "mouse")
        self.assertEqual(self.user.shared_inbox, f"{self.protocol}{DOMAIN}/inbox")
        self.assertEqual(self.user.inbox, f"{expected_id}/inbox")
        self.assertEqual(self.user.outbox, f"{expected_id}/outbox")
        self.assertEqual(self.user.followers_url, f"{expected_id}/followers")
        self.assertIsNotNone(self.user.key_pair.private_key)
        self.assertIsNotNone(self.user.key_pair.public_key)

    def test_remote_user(self):
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                local=False,
                remote_id="https://example.com/dfjkg",
                bookwyrm_user=False,
            )
        self.assertEqual(user.username, "rat@example.com")

    def test_user_shelves(self):
        shelves = models.Shelf.objects.filter(user=self.user).all()
        self.assertEqual(len(shelves), 3)
        names = [s.name for s in shelves]
        self.assertTrue("To Read" in names)
        self.assertTrue("Currently Reading" in names)
        self.assertTrue("Read" in names)
        ids = [s.identifier for s in shelves]
        self.assertTrue("to-read" in ids)
        self.assertTrue("reading" in ids)
        self.assertTrue("read" in ids)

    def test_activitypub_serialize(self):
        activity = self.user.to_activity()
        self.assertEqual(activity["id"], self.user.remote_id)
        self.assertEqual(
            activity["@context"],
            [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1",
                {
                    "manuallyApprovesFollowers": "as:manuallyApprovesFollowers",
                    "schema": "http://schema.org#",
                    "PropertyValue": "schema:PropertyValue",
                    "value": "schema:value",
                },
            ],
        )
        self.assertEqual(activity["preferredUsername"], self.user.localname)
        self.assertEqual(activity["name"], self.user.name)
        self.assertEqual(activity["inbox"], self.user.inbox)
        self.assertEqual(activity["outbox"], self.user.outbox)
        self.assertEqual(activity["bookwyrmUser"], False)
        self.assertEqual(activity["discoverable"], False)
        self.assertEqual(activity["type"], "Person")

    def test_activitypub_outbox(self):
        activity = self.user.to_outbox()
        self.assertEqual(activity["type"], "OrderedCollection")
        self.assertEqual(activity["id"], self.user.outbox)
        self.assertEqual(activity["totalItems"], 0)

    def test_set_remote_server(self):
        server = models.FederatedServer.objects.create(
            server_name=DOMAIN, application_type="test type", application_version=3
        )

        models.user.set_remote_server(self.user.id)
        self.user.refresh_from_db()

        self.assertEqual(self.user.federated_server, server)

    @responses.activate
    def test_get_or_create_remote_server(self):
        responses.add(
            responses.GET,
            f"https://{DOMAIN}/.well-known/nodeinfo",
            json={"links": [{"href": "http://www.example.com"}, {}]},
        )
        responses.add(
            responses.GET,
            "http://www.example.com",
            json={"software": {"name": "hi", "version": "2"}},
        )

        server = models.user.get_or_create_remote_server(DOMAIN)
        self.assertEqual(server.server_name, DOMAIN)
        self.assertEqual(server.application_type, "hi")
        self.assertEqual(server.application_version, "2")

    @responses.activate
    def test_get_or_create_remote_server_no_wellknown(self):
        responses.add(
            responses.GET, f"https://{DOMAIN}/.well-known/nodeinfo", status=404
        )

        server = models.user.get_or_create_remote_server(DOMAIN)
        self.assertEqual(server.server_name, DOMAIN)
        self.assertIsNone(server.application_type)
        self.assertIsNone(server.application_version)

    @responses.activate
    def test_get_or_create_remote_server_no_links(self):
        responses.add(
            responses.GET,
            f"https://{DOMAIN}/.well-known/nodeinfo",
            json={"links": [{"href": "http://www.example.com"}, {}]},
        )
        responses.add(responses.GET, "http://www.example.com", status=404)

        server = models.user.get_or_create_remote_server(DOMAIN)
        self.assertEqual(server.server_name, DOMAIN)
        self.assertIsNone(server.application_type)
        self.assertIsNone(server.application_version)

    @responses.activate
    def test_get_or_create_remote_server_unknown_format(self):
        responses.add(
            responses.GET,
            f"https://{DOMAIN}/.well-known/nodeinfo",
            json={"links": [{"href": "http://www.example.com"}, {}]},
        )
        responses.add(responses.GET, "http://www.example.com", json={"fish": "salmon"})

        server = models.user.get_or_create_remote_server(DOMAIN)
        self.assertEqual(server.server_name, DOMAIN)
        self.assertIsNone(server.application_type)
        self.assertIsNone(server.application_version)

    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_delete_user(self, _):
        """deactivate a user"""
        self.assertTrue(self.user.is_active)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as broadcast_mock:
            self.user.delete()

        self.assertEqual(broadcast_mock.call_count, 1)
        activity = json.loads(broadcast_mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["object"], self.user.remote_id)
        self.assertFalse(self.user.is_active)
