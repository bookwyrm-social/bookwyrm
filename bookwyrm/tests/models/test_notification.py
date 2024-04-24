""" testing models """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import models


class Notification(TestCase):
    """let people know things"""

    @classmethod
    def setUpTestData(cls):
        """useful things for creating a notification"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
            cls.another_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )
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
        cls.work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Test Book",
            isbn_13="1234567890123",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )
        cls.another_book = models.Edition.objects.create(
            title="Second Test Book",
            parent_work=models.Work.objects.create(title="Test Work"),
        )

    def test_notification(self):
        """New notifications are unread"""
        notification = models.Notification.objects.create(
            user=self.local_user, notification_type=models.NotificationType.FAVORITE
        )
        self.assertFalse(notification.read)

    def test_notify(self):
        """Create a notification"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

    def test_notify_grouping(self):
        """Bundle notifications"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertEqual(models.Notification.objects.count(), 1)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.related_users.count(), 1)

        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type=models.NotificationType.FAVORITE,
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
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())

    def test_notify_self(self):
        """Don't create notifications for yourself"""
        models.Notification.notify(
            self.local_user,
            self.local_user,
            notification_type=models.NotificationType.FAVORITE,
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
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.remote_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())

    def test_unnotify_multiple_users(self):
        """Remove a notification"""
        models.Notification.notify(
            self.local_user,
            self.remote_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.remote_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertTrue(models.Notification.objects.exists())

        models.Notification.unnotify(
            self.local_user,
            self.another_user,
            notification_type=models.NotificationType.FAVORITE,
        )
        self.assertFalse(models.Notification.objects.exists())


class NotifyInviteRequest(TestCase):
    """let admins know of invite requests"""

    @classmethod
    def setUpTestData(cls):
        """ensure there is one admin"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
                is_superuser=True,
            )

    def test_invite_request_triggers_notification(self):
        """requesting an invite notifies the admin"""
        admin = models.User.objects.filter(is_superuser=True).first()
        request = models.InviteRequest.objects.create(email="user@example.com")

        self.assertEqual(models.Notification.objects.count(), 1)

        notification = models.Notification.objects.first()
        self.assertEqual(notification.user, admin)
        self.assertEqual(
            notification.notification_type, models.NotificationType.INVITE_REQUEST
        )
        self.assertEqual(notification.related_invite_requests.count(), 1)
        self.assertEqual(notification.related_invite_requests.first(), request)

    def test_notify_only_created(self):
        """updating an invite request does not trigger a notification"""
        request = models.InviteRequest.objects.create(email="user@example.com")
        notification = models.Notification.objects.first()

        notification.delete()
        self.assertEqual(models.Notification.objects.count(), 0)

        request.ignored = True
        request.save()
        self.assertEqual(models.Notification.objects.count(), 0)

    def test_notify_grouping(self):
        """invites group into the same notification, until read"""
        requests = [
            models.InviteRequest.objects.create(email="user1@example.com"),
            models.InviteRequest.objects.create(email="user2@example.com"),
        ]
        self.assertEqual(models.Notification.objects.count(), 1)

        notification = models.Notification.objects.first()
        self.assertEqual(notification.related_invite_requests.count(), 2)
        self.assertCountEqual(notification.related_invite_requests.all(), requests)

        notification.read = True
        notification.save()

        request = models.InviteRequest.objects.create(email="user3@example.com")
        _, notification = models.Notification.objects.all()

        self.assertEqual(models.Notification.objects.count(), 2)
        self.assertEqual(notification.related_invite_requests.count(), 1)
        self.assertEqual(notification.related_invite_requests.first(), request)

    def test_notify_multiple_admins(self):
        """all admins are notified"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            self.local_user = models.User.objects.create_user(
                "admin@local.com",
                "admin@example.com",
                "password",
                local=True,
                localname="root",
                is_superuser=True,
            )
            models.InviteRequest.objects.create(email="user@example.com")
            admins = models.User.objects.filter(is_superuser=True).all()
            notifications = models.Notification.objects.all()

            self.assertEqual(len(notifications), 2)
            self.assertCountEqual([notif.user for notif in notifications], admins)
