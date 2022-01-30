""" tests updating reading progress """
from datetime import datetime
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone

from bookwyrm import models


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.remove_book_statuses_task.delay")
class ReadThrough(TestCase):
    """readthrough tests"""

    def setUp(self):
        """basic user and book data"""
        self.client = Client()

        self.work = models.Work.objects.create(title="Example Work")

        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )

        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
                "cinco", "cinco@example.com", "seissiete", local=True, localname="cinco"
            )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.client.force_login(self.user)

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    def test_create_basic_readthrough(self, *_):
        """A basic readthrough doesn't create a progress update"""
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post(
            f"/reading-status/start/{self.edition.id}",
            {"start_date": "2020-11-27"},
        )

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(readthroughs[0].progressupdate_set.count(), 0)
        self.assertEqual(
            readthroughs[0].start_date, datetime(2020, 11, 27, tzinfo=timezone.utc)
        )
        self.assertEqual(readthroughs[0].progress, None)
        self.assertEqual(readthroughs[0].finish_date, None)

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    def test_create_progress_readthrough(self, *_):
        """a readthrough with progress"""
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post(
            f"/reading-status/start/{self.edition.id}",
            {"start_date": "2020-11-27"},
        )

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(
            readthroughs[0].start_date, datetime(2020, 11, 27, tzinfo=timezone.utc)
        )
        self.assertEqual(readthroughs[0].finish_date, None)

        # Update progress
        self.client.post(
            "/edit-readthrough",
            {
                "id": readthroughs[0].id,
                "progress": 100,
            },
        )

        progress_updates = (
            readthroughs[0].progressupdate_set.order_by("updated_date").all()
        )
        self.assertEqual(len(progress_updates), 1)
        self.assertEqual(progress_updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(progress_updates[0].progress, 100)

        # Edit doesn't publish anything
        self.client.post(
            "/delete-readthrough",
            {
                "id": readthroughs[0].id,
            },
        )

        readthroughs = self.edition.readthrough_set.all()
        updates = self.user.progressupdate_set.all()
        self.assertEqual(len(readthroughs), 0)
        self.assertEqual(len(updates), 0)
