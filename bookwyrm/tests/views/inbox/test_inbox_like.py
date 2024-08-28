""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


class InboxActivities(TestCase):
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

        with (
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.activitystreams.add_status_task.delay"),
        ):
            cls.status = models.Status.objects.create(
                user=cls.local_user,
                content="Test status",
                remote_id="https://example.com/status/1",
            )

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }

    def test_handle_favorite(self):
        """fav a status"""
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/fav/1",
            "actor": "https://example.com/users/rat",
            "type": "Like",
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "object": self.status.remote_id,
        }

        views.inbox.activity_task(activity)

        fav = models.Favorite.objects.get(remote_id="https://example.com/fav/1")
        self.assertEqual(fav.status, self.status)
        self.assertEqual(fav.remote_id, "https://example.com/fav/1")
        self.assertEqual(fav.user, self.remote_user)

    def test_ignore_favorite(self):
        """don't try to save an unknown status"""
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/fav/1",
            "actor": "https://example.com/users/rat",
            "type": "Like",
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "object": "https://unknown.status/not-found",
        }

        views.inbox.activity_task(activity)

        self.assertFalse(models.Favorite.objects.exists())

    def test_handle_unfavorite(self):
        """fav a status"""
        activity = {
            "id": "https://example.com/fav/1#undo",
            "type": "Undo",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": "https://example.com/fav/1",
                "actor": "https://example.com/users/rat",
                "type": "Like",
                "published": "Mon, 25 May 2020 19:31:20 GMT",
                "object": self.status.remote_id,
            },
        }
        models.Favorite.objects.create(
            status=self.status,
            user=self.remote_user,
            remote_id="https://example.com/fav/1",
        )
        self.assertEqual(models.Favorite.objects.count(), 1)

        views.inbox.activity_task(activity)
        self.assertEqual(models.Favorite.objects.count(), 0)
