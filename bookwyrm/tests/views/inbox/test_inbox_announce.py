""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxActivities(TestCase):
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
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
                self.status = models.Status.objects.create(
                    user=self.local_user,
                    content="Test status",
                    remote_id="https://example.com/status/1",
                )

        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    @patch("bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores")
    def test_boost(self, redis_mock, _):
        """boost a status"""
        self.assertEqual(models.Notification.objects.count(), 0)
        activity = {
            "type": "Announce",
            "id": "%s/boost" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": self.status.remote_id,
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "published": "Mon, 25 May 2020 19:31:20 GMT",
        }
        with patch("bookwyrm.models.status.Status.ignore_activity") as discarder:
            discarder.return_value = False
            views.inbox.activity_task(activity)

        # boost added to redis activitystreams
        self.assertTrue(redis_mock.called)

        # boost created of correct status
        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status, self.status)

        # notification sent to original poster
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_status, self.status)

    @responses.activate
    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    @patch("bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores")
    def test_boost_remote_status(self, redis_mock, _):
        """boost a status from a remote server"""
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )
        self.assertEqual(models.Notification.objects.count(), 0)
        activity = {
            "type": "Announce",
            "id": "%s/boost" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": "https://remote.com/status/1",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "published": "Mon, 25 May 2020 19:31:20 GMT",
        }
        responses.add(
            responses.GET,
            "https://remote.com/status/1",
            json={
                "id": "https://remote.com/status/1",
                "type": "Comment",
                "published": "2021-04-05T18:04:59.735190+00:00",
                "attributedTo": self.remote_user.remote_id,
                "content": "<p>a comment</p>",
                "to": ["https://www.w3.org/ns/activitystreams#Public"],
                "cc": ["https://b875df3d118b.ngrok.io/user/mouse/followers"],
                "inReplyTo": "",
                "inReplyToBook": book.remote_id,
                "summary": "",
                "tag": [],
                "sensitive": False,
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        with patch("bookwyrm.models.status.Status.ignore_activity") as discarder:
            discarder.return_value = False
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)

        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status.remote_id, "https://remote.com/status/1")
        self.assertEqual(boost.boosted_status.comment.status_type, "Comment")
        self.assertEqual(boost.boosted_status.comment.book, book)

    @responses.activate
    def test_discarded_boost(self):
        """test a boost of a mastodon status that will be discarded"""
        status = models.Status(
            content="hi",
            user=self.remote_user,
        )
        with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
            status.save(broadcast=False)
        activity = {
            "type": "Announce",
            "id": "http://www.faraway.com/boost/12",
            "actor": self.remote_user.remote_id,
            "object": status.remote_id,
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "published": "Mon, 25 May 2020 19:31:20 GMT",
        }
        responses.add(
            responses.GET, status.remote_id, json=status.to_activity(), status=200
        )
        views.inbox.activity_task(activity)
        self.assertEqual(models.Boost.objects.count(), 0)

    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    @patch("bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores")
    def test_unboost(self, *_):
        """undo a boost"""
        boost = models.Boost.objects.create(
            boosted_status=self.status, user=self.remote_user
        )
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "type": "Announce",
                "id": boost.remote_id,
                "actor": self.remote_user.remote_id,
                "object": self.status.remote_id,
                "to": ["https://www.w3.org/ns/activitystreams#public"],
                "cc": ["https://example.com/user/mouse/followers"],
                "published": "Mon, 25 May 2020 19:31:20 GMT",
            },
        }
        views.inbox.activity_task(activity)
        self.assertFalse(models.Boost.objects.exists())

    def test_unboost_unknown_boost(self):
        """undo a boost"""
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "type": "Announce",
                "id": "http://fake.com/unknown/boost",
                "actor": self.remote_user.remote_id,
                "object": self.status.remote_id,
                "published": "Mon, 25 May 2020 19:31:20 GMT",
            },
        }
        views.inbox.activity_task(activity)
