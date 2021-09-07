"""tests incoming activities"""
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxActivities(TestCase):
    """inbox tests"""

    def setUp(self):
        """basic user and book data"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
            )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False, update_fields=["remote_id"])
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
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            self.status = models.Status.objects.create(
                user=self.remote_user,
                content="Test status",
                remote_id="https://example.com/status/1",
            )

        models.SiteSettings.objects.create()

    def test_delete_status(self):
        """remove a status"""
        self.assertFalse(self.status.deleted)
        activity = {
            "type": "Delete",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "id": "%s/activity" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": {"id": self.status.remote_id, "type": "Tombstone"},
        }
        with patch("bookwyrm.activitystreams.remove_status_task.delay") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)

    def test_delete_status_notifications(self):
        """remove a status with related notifications"""
        models.Notification.objects.create(
            related_status=self.status,
            user=self.local_user,
            notification_type="MENTION",
        )
        # this one is innocent, don't delete it
        notif = models.Notification.objects.create(
            user=self.local_user, notification_type="MENTION"
        )
        self.assertFalse(self.status.deleted)
        self.assertEqual(models.Notification.objects.count(), 2)
        activity = {
            "type": "Delete",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "id": "%s/activity" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": {"id": self.status.remote_id, "type": "Tombstone"},
        }
        with patch("bookwyrm.activitystreams.remove_status_task.delay") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)

        # notifications should be truly deleted
        self.assertEqual(models.Notification.objects.count(), 1)
        self.assertEqual(models.Notification.objects.get(), notif)

    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_delete_user(self, _):
        """delete a user"""
        self.assertTrue(models.User.objects.get(username="rat@example.com").is_active)
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/test-user#delete",
            "type": "Delete",
            "actor": "https://example.com/users/test-user",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "object": self.remote_user.remote_id,
        }

        views.inbox.activity_task(activity)
        self.assertFalse(models.User.objects.get(username="rat@example.com").is_active)

    def test_delete_user_unknown(self):
        """don't worry about it if we don't know the user"""
        self.assertEqual(models.User.objects.filter(is_active=True).count(), 2)
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/test-user#delete",
            "type": "Delete",
            "actor": "https://example.com/users/test-user",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "object": "https://example.com/users/test-user",
        }

        # nothing happens.
        views.inbox.activity_task(activity)
        self.assertEqual(models.User.objects.filter(is_active=True).count(), 2)

    def test_delete_list(self):
        """delete a list"""
        book_list = models.List.objects.create(
            name="test list",
            user=self.remote_user,
            remote_id="https://example.com/list/1",
        )
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/test-user#delete",
            "type": "Delete",
            "actor": "https://example.com/users/test-user",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "object": {
                "id": book_list.remote_id,
                "owner": self.remote_user.remote_id,
                "type": "BookList",
                "totalItems": 0,
                "first": "",
                "name": "test list",
                "to": [],
                "cc": [],
            },
        }
        views.inbox.activity_task(activity)
        self.assertFalse(models.List.objects.exists())
