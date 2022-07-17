""" testing models """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import models


class Notification(TestCase):
    """let people know things"""

    def setUp(self):  # pylint: disable=invalid-name
        """useful things for creating a notification"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
            self.another_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )
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
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Test Book",
            isbn_13="1234567890123",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        self.another_book = models.Edition.objects.create(
            title="Second Test Book",
            parent_work=models.Work.objects.create(title="Test Work"),
        )

    def test_notification(self):
        """New notifications are unread"""
        notification = models.Notification.objects.create(
            user=self.local_user, notification_type=models.Notification.FAVORITE
        )
        self.assertFalse(notification.read)

    def test_notify(self):
        """Create a notification"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

    def test_notify_grouping(self):
        """Bundle notifications"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertEqual(models.Notification.objects.count(), 1)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.related_users.count(), 1)

        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertEqual(models.Notification.objects.count(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.related_users.count(), 2)

    def test_notify_grouping_with_dupes(self):
        """If there are multiple options to group with, don't cause an error"""
        models.Notification.objects.create(
            user=self.local_user, notification_type="FAVORITE"
        )
        models.Notification.objects.create(
            user=self.local_user, notification_type="FAVORITE"
        )
        models.Notification.notify(self.local_user, None, notification_type="FAVORITE")
        self.assertEqual(models.Notification.objects.count(), 2)

    def test_notify_remote(self):
        """Don't create notifications for remote users"""
        models.Notification.notify(
            self.remote_user,
            self.local_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())

    def test_notify_self(self):
        """Don't create notifications for yourself"""
        models.Notification.notify(
            self.local_user,
            self.local_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.lists_stream.remove_list_task.delay")
    def test_notify_list_item_own_list(self, *_):
        """Don't add list item notification for your own list"""
        test_list = models.List.objects.create(user=self.local_user, name="hi")

        models.ListItem.objects.create(
            user=self.local_user, book=self.book, book_list=test_list, order=1
        )
        self.assertFalse(models.Notification.objects.exists())

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.lists_stream.remove_list_task.delay")
    def test_notify_list_item_remote(self, *_):
        """Don't add list item notification for a remote user"""
        test_list = models.List.objects.create(user=self.remote_user, name="hi")

        models.ListItem.objects.create(
            user=self.local_user, book=self.book, book_list=test_list, order=1
        )
        self.assertFalse(models.Notification.objects.exists())

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.lists_stream.remove_list_task.delay")
    def test_notify_list_item(self, *_):
        """Add list item notification"""
        test_list = models.List.objects.create(user=self.local_user, name="hi")
        list_item = models.ListItem.objects.create(
            user=self.remote_user, book=self.book, book_list=test_list, order=2
        )
        notification = models.Notification.objects.get()
        self.assertEqual(notification.related_users.count(), 1)
        self.assertEqual(notification.related_users.first(), self.remote_user)
        self.assertEqual(notification.related_list_items.count(), 1)
        self.assertEqual(notification.related_list_items.first(), list_item)

        models.ListItem.objects.create(
            user=self.remote_user, book=self.another_book, book_list=test_list, order=3
        )
        notification = models.Notification.objects.get()
        self.assertEqual(notification.related_users.count(), 1)
        self.assertEqual(notification.related_users.first(), self.remote_user)
        self.assertEqual(notification.related_list_items.count(), 2)

    def test_unnotify(self):
        """Remove a notification"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())

    def test_unnotify_multiple_users(self):
        """Remove a notification"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.remote_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.another_user,
            notification_type=models.Notification.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())
