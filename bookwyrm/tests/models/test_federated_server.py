""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


class FederatedServer(TestCase):
    """federate server management"""

    def setUp(self):
        """we'll need a user"""
        self.server = models.FederatedServer.objects.create(server_name="test.server")
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                federated_server=self.server,
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
            self.inactive_remote_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.com",
                "nutriaword",
                federated_server=self.server,
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                outbox="https://example.com/users/nutria/outbox",
                is_active=False,
                deactivation_reason="self_deletion",
            )

    def test_block_unblock(self):
        """block a server and all users on it"""
        self.assertEqual(self.server.status, "federated")
        self.assertTrue(self.remote_user.is_active)
        self.assertFalse(self.inactive_remote_user.is_active)

        self.server.block()

        self.assertEqual(self.server.status, "blocked")
        self.remote_user.refresh_from_db()
        self.assertFalse(self.remote_user.is_active)
        self.assertEqual(self.remote_user.deactivation_reason, "domain_block")

        self.inactive_remote_user.refresh_from_db()
        self.assertFalse(self.inactive_remote_user.is_active)
        self.assertEqual(self.inactive_remote_user.deactivation_reason, "self_deletion")

        # UNBLOCK
        self.server.unblock()

        self.assertEqual(self.server.status, "federated")
        # user blocked in deactivation is reactivated
        self.remote_user.refresh_from_db()
        self.assertTrue(self.remote_user.is_active)
        self.assertIsNone(self.remote_user.deactivation_reason)

        # deleted user remains deleted
        self.inactive_remote_user.refresh_from_db()
        self.assertFalse(self.inactive_remote_user.is_active)
        self.assertEqual(self.inactive_remote_user.deactivation_reason, "self_deletion")
