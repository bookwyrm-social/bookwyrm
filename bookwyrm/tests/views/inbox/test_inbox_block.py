""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


class InboxBlock(TestCase):
    """inbox tests"""

    @classmethod
    def setUpTestData(cls):
        """basic user and book data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
            )
        cls.local_user.remote_id = "https://example.com/user/mouse"
        cls.local_user.save(broadcast=False, update_fields=["remote_id"])
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        models.SiteSettings.objects.create()

    def test_handle_blocks(self):
        """create a "block" database entry from an activity"""
        self.local_user.followers.add(self.remote_user)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        self.assertTrue(models.UserFollows.objects.exists())
        self.assertTrue(models.UserFollowRequest.objects.exists())

        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/9e1f41ac-9ddd-4159",
            "type": "Block",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        with (
            patch(
                "bookwyrm.activitystreams.remove_user_statuses_task.delay"
            ) as redis_mock,
            patch("bookwyrm.lists_stream.remove_user_lists_task.delay"),
        ):
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        views.inbox.activity_task(activity)
        block = models.UserBlocks.objects.get()
        self.assertEqual(block.user_subject, self.remote_user)
        self.assertEqual(block.user_object, self.local_user)
        self.assertEqual(block.remote_id, "https://example.com/9e1f41ac-9ddd-4159")

        self.assertFalse(models.UserFollows.objects.exists())
        self.assertFalse(models.UserFollowRequest.objects.exists())

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    @patch("bookwyrm.lists_stream.add_user_lists_task.delay")
    @patch("bookwyrm.lists_stream.remove_user_lists_task.delay")
    def test_handle_unblock(self, *_):
        """unblock a user"""
        self.remote_user.blocks.add(self.local_user)

        block = models.UserBlocks.objects.get()
        block.remote_id = "https://example.com/9e1f41ac-9ddd-4159"
        block.save()

        self.assertEqual(block.user_subject, self.remote_user)
        self.assertEqual(block.user_object, self.local_user)
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": "https://example.com/9e1f41ac-9ddd-4159",
                "type": "Block",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }
        with patch(
            "bookwyrm.activitystreams.add_user_statuses_task.delay"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        self.assertFalse(models.UserBlocks.objects.exists())
