""" testing activitystreams """
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookwyrm import activitystreams, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.lists_stream.add_user_lists_task.delay")
@patch("bookwyrm.lists_stream.remove_user_lists_task.delay")
class ActivitystreamsSignals(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )
            self.another_user = models.User.objects.create_user(
                "fish", "fish@fish.fish", "password", local=True, localname="fish"
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

    def test_add_status_on_create_ignore(self, *_):
        """a new statuses has entered"""
        activitystreams.add_status_on_create(models.User, self.local_user, False)

    def test_add_status_on_create_deleted(self, *_):
        """a new statuses has entered"""
        with patch("bookwyrm.activitystreams.remove_status_task.delay"):
            status = models.Status.objects.create(
                user=self.remote_user, content="hi", privacy="public", deleted=True
            )
        with patch("bookwyrm.activitystreams.remove_status_task.delay") as mock:
            activitystreams.add_status_on_create(models.Status, status, False)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], status.id)

    def test_add_status_on_create_created(self, *_):
        """a new statuses has entered"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "high_priority")

    def test_add_status_on_create_created_low_priority(self, *_):
        """a new statuses has entered"""
        # created later than publication
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="public",
            created_date=datetime(2022, 5, 16, tzinfo=timezone.utc),
            published_date=datetime(2022, 5, 14, tzinfo=timezone.utc),
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)

        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "low_priority")

        # published later than yesterday
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="public",
            published_date=timezone.now() - timedelta(days=1),
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)

        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "low_priority")

    def test_populate_streams_on_account_create_command(self, *_):
        """create streams for a user"""
        with patch("bookwyrm.activitystreams.populate_stream_task.delay") as mock:
            activitystreams.populate_streams_on_account_create_command(
                self.local_user.id
            )
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], "books")
        self.assertEqual(args[1], self.local_user.id)

    def test_remove_statuses_on_block(self, *_):
        """don't show statuses from blocked users"""
        with patch("bookwyrm.activitystreams.remove_user_statuses_task.delay") as mock:
            models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    def test_add_statuses_on_unblock(self, *_):
        """re-add statuses on unblock"""
        with patch("bookwyrm.activitystreams.remove_user_statuses_task.delay"):
            block = models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        with patch("bookwyrm.activitystreams.add_user_statuses_task.delay") as mock:
            block.delete()

        args = mock.call_args[0]
        kwargs = mock.call_args.kwargs
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)
        self.assertEqual(kwargs["stream_list"], ["local", "books"])

    def test_add_statuses_on_unblock_reciprocal_block(self, *_):
        """re-add statuses on unblock"""
        with patch("bookwyrm.activitystreams.remove_user_statuses_task.delay"):
            block = models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )
            block = models.UserBlocks.objects.create(
                user_subject=self.remote_user,
                user_object=self.local_user,
            )

        with patch("bookwyrm.activitystreams.add_user_statuses_task.delay") as mock:
            block.delete()

        self.assertEqual(mock.call_count, 0)
