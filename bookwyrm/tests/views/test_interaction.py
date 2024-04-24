""" test for app action functionality """
import json
from unittest.mock import patch
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class InteractionViews(TestCase):
    """viewing and creating statuses"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        with patch("bookwyrm.models.user.set_remote_server"):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@email.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_favorite(self, *_):
        """create and broadcast faving a status"""
        view = views.Favorite.as_view()
        request = self.factory.post("")
        request.user = self.remote_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")

            view(request, status.id)
        fav = models.Favorite.objects.get()
        self.assertEqual(fav.status, status)
        self.assertEqual(fav.user, self.remote_user)

        notification = models.Notification.objects.get()
        self.assertEqual(notification.notification_type, "FAVORITE")
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_users.first(), self.remote_user)

    def test_unfavorite(self, *_):
        """unfav a status"""
        view = views.Unfavorite.as_view()
        request = self.factory.post("")
        request.user = self.remote_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")
            views.Favorite.as_view()(request, status.id)

        self.assertEqual(models.Favorite.objects.count(), 1)
        self.assertEqual(models.Notification.objects.count(), 1)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, status.id)
        self.assertEqual(models.Favorite.objects.count(), 0)
        self.assertEqual(models.Notification.objects.count(), 0)

    def test_boost(self, *_):
        """boost a status"""
        view = views.Boost.as_view()
        request = self.factory.post("")
        request.user = self.remote_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")

            view(request, status.id)

        boost = models.Boost.objects.get()

        self.assertEqual(boost.boosted_status, status)
        self.assertEqual(boost.user, self.remote_user)
        self.assertEqual(boost.privacy, "public")

        notification = models.Notification.objects.get()
        self.assertEqual(notification.notification_type, "BOOST")
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_users.first(), self.remote_user)
        self.assertEqual(notification.related_status, status)

    def test_self_boost(self, *_):
        """boost your own status"""
        view = views.Boost.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")

            with patch(
                "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
            ) as broadcast_mock:
                view(request, status.id)

        self.assertEqual(broadcast_mock.call_count, 1)
        activity = json.loads(broadcast_mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Announce")

        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status, status)
        self.assertEqual(boost.user, self.local_user)
        self.assertEqual(boost.privacy, "public")

        self.assertFalse(models.Notification.objects.exists())

    def test_boost_unlisted(self, *_):
        """boost a status"""
        view = views.Boost.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(
                user=self.local_user, content="hi", privacy="unlisted"
            )

            view(request, status.id)

        boost = models.Boost.objects.get()
        self.assertEqual(boost.privacy, "unlisted")

    def test_boost_private(self, *_):
        """boost a status"""
        view = views.Boost.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(
                user=self.local_user, content="hi", privacy="followers"
            )

            view(request, status.id)
        self.assertFalse(models.Boost.objects.exists())

    def test_boost_twice(self, *_):
        """boost a status"""
        view = views.Boost.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(user=self.local_user, content="hi")

            view(request, status.id)
            view(request, status.id)
        self.assertEqual(models.Boost.objects.count(), 1)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_unboost(self, *_):
        """undo a boost"""
        view = views.Unboost.as_view()
        request = self.factory.post("")
        request.user = self.remote_user
        status = models.Status.objects.create(user=self.local_user, content="hi")

        views.Boost.as_view()(request, status.id)

        self.assertEqual(models.Boost.objects.count(), 1)
        self.assertEqual(models.Notification.objects.count(), 1)

        view(request, status.id)

        self.assertEqual(models.Boost.objects.count(), 0)
        self.assertEqual(models.Notification.objects.count(), 0)
