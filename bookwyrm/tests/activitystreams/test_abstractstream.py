""" testing activitystreams """
from datetime import datetime
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from bookwyrm import activitystreams, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )
            self.another_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.nutria",
                "password",
                local=True,
                localname="nutria",
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
        work = models.Work.objects.create(title="test work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)

    def setUp(self):
        """per-test setUp"""

        class TestStream(activitystreams.ActivityStream):
            """test stream, don't have to do anything here"""

            key = "test"

        self.test_stream = TestStream()

    def test_activitystream_class_ids(self, *_):
        """the abstract base class for stream objects"""
        self.assertEqual(
            self.test_stream.stream_id(self.local_user.id),
            f"{self.local_user.id}-test",
        )
        self.assertEqual(
            self.test_stream.unread_id(self.local_user.id),
            f"{self.local_user.id}-test-unread",
        )

    def test_unread_by_status_type_id(self, *_):
        """stream for status type"""
        self.assertEqual(
            self.test_stream.unread_by_status_type_id(self.local_user.id),
            f"{self.local_user.id}-test-unread-by-type",
        )

    def test_get_rank(self, *_):
        """sort order"""
        date = datetime(2022, 1, 28, 0, 0, tzinfo=timezone.utc)
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            published_date=date,
        )
        self.assertEqual(
            str(self.test_stream.get_rank(status)),
            "1643328000.0",
        )

    def test_get_activity_stream(self, *_):
        """load statuses"""
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
        )
        status2 = models.Comment.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        models.Comment.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        with patch("bookwyrm.activitystreams.r.set"), patch(
            "bookwyrm.activitystreams.r.delete"
        ), patch("bookwyrm.activitystreams.ActivityStream.get_store") as redis_mock:
            redis_mock.return_value = [status.id, status2.id]
            result = self.test_stream.get_activity_stream(self.local_user)
        self.assertEqual(result.count(), 2)
        self.assertEqual(result.first(), status2)
        self.assertEqual(result.last(), status)
        self.assertIsInstance(result.first(), models.Comment)

    def test_abstractstream_get_audience(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = self.test_stream.get_audience(status)
        # remote users don't have feeds
        self.assertFalse(self.remote_user.id in users)
        self.assertTrue(self.local_user.id in users)
        self.assertTrue(self.another_user.id in users)

    def test_abstractstream_get_audience_direct(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
        )
        status.mention_users.add(self.local_user)
        users = self.test_stream.get_audience(status)
        self.assertEqual(users, [])

        status = models.Comment.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        status.mention_users.add(self.local_user)
        users = self.test_stream.get_audience(status)
        self.assertTrue(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)
        self.assertFalse(self.remote_user.id in users)

    def test_abstractstream_get_audience_followers_remote_user(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="followers",
        )
        users = self.test_stream.get_audience(status)
        self.assertEqual(users, [])

    def test_abstractstream_get_audience_followers_self(self, *_):
        """get a list of users that should see a status"""
        status = models.Comment.objects.create(
            user=self.local_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        users = self.test_stream.get_audience(status)
        self.assertTrue(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)
        self.assertFalse(self.remote_user.id in users)

    def test_abstractstream_get_audience_followers_with_mention(self, *_):
        """get a list of users that should see a status"""
        status = models.Comment.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        status.mention_users.add(self.local_user)

        users = self.test_stream.get_audience(status)
        self.assertTrue(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)
        self.assertFalse(self.remote_user.id in users)

    def test_abstractstream_get_audience_followers_with_relationship(self, *_):
        """get a list of users that should see a status"""
        self.remote_user.followers.add(self.local_user)
        status = models.Comment.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="direct",
            book=self.book,
        )
        users = self.test_stream.get_audience(status)
        self.assertFalse(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)
        self.assertFalse(self.remote_user.id in users)
