""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxBlock(TestCase):
    """inbox tests"""

    def setUp(self):
        """basic user and book data"""
        self.local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False)
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

        models.SiteSettings.objects.create()

    def test_handle_blocks(self):
        """create a "block" database entry from an activity"""
        self.local_user.followers.add(self.remote_user)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
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

        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_user_statuses"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        views.inbox.activity_task(activity)
        block = models.UserBlocks.objects.get()
        self.assertEqual(block.user_subject, self.remote_user)
        self.assertEqual(block.user_object, self.local_user)
        self.assertEqual(block.remote_id, "https://example.com/9e1f41ac-9ddd-4159")

        self.assertFalse(models.UserFollows.objects.exists())
        self.assertFalse(models.UserFollowRequest.objects.exists())

    def test_handle_unblock(self):
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
            "bookwyrm.activitystreams.ActivityStream.add_user_statuses"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        self.assertFalse(models.UserBlocks.objects.exists())
