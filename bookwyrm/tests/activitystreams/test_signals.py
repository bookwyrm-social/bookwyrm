""" testing activitystreams """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import activitystreams, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class ActivitystreamsSignals(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
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

    def test_add_status_on_create_ignore(self, _):
        """a new statuses has entered"""
        activitystreams.add_status_on_create(models.User, self.local_user, False)

    def test_add_status_on_create_deleted(self, _):
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

    def test_add_status_on_create_created(self, _):
        """a new statuses has entered"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        with patch("bookwyrm.activitystreams.add_status_task.delay") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], status.id)

    def test_populate_streams_on_account_create(self, _):
        """create streams for a user"""
        with patch("bookwyrm.activitystreams.populate_stream_task.delay") as mock:
            activitystreams.populate_streams_on_account_create(
                models.User, self.local_user, True
            )
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], "books")
        self.assertEqual(args[1], self.local_user.id)
