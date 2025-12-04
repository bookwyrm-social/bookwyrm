"""testing move models"""

from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from bookwyrm import models


class MoveUser(TestCase):
    """move your account to another identity"""

    @classmethod
    def setUpTestData(cls):
        """we need some users for this"""
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            cls.target_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.origin_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
            )
        cls.origin_user.remote_id = "http://local.com/user/mouse"
        cls.origin_user.save(broadcast=False, update_fields=["remote_id"])

    def test_user_move_unauthorized(self):
        """attempt a user move without alsoKnownAs set"""

        with self.assertRaises(PermissionDenied):
            models.MoveUser.objects.create(
                user=self.origin_user,
                object=self.origin_user.remote_id,
                target=self.target_user,
            )

    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    def test_user_move(self, *_):
        """move user"""

        self.target_user.also_known_as.add(self.origin_user.id)
        self.target_user.save(broadcast=False)

        models.MoveUser.objects.create(
            user=self.origin_user,
            object=self.origin_user.remote_id,
            target=self.target_user,
        )
        self.assertEqual(self.origin_user.moved_to, self.target_user.remote_id)
