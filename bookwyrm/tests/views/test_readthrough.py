""" tests updating reading progress """
from datetime import datetime
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone

from bookwyrm import models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class ReadThrough(TestCase):
    """readthrough tests"""

    def setUp(self):
        """basic user and book data"""
        self.client = Client()

        self.work = models.Work.objects.create(title="Example Work")

        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )

        self.user = models.User.objects.create_user(
            "cinco", "cinco@example.com", "seissiete", local=True, localname="cinco"
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.client.force_login(self.user)

    def test_create_basic_readthrough(self, delay_mock):
        """A basic readthrough doesn't create a progress update"""
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post(
            "/reading-status/start/{}".format(self.edition.id),
            {
                "start_date": "2020-11-27",
            },
        )

        readthroughs = self.edition.readthrough_set.all()
        self.assertEqual(len(readthroughs), 1)
        self.assertEqual(readthroughs[0].progressupdate_set.count(), 0)
        self.assertEqual(
            readthroughs[0].start_date, datetime(2020, 11, 27, tzinfo=timezone.utc)
        )
        self.assertEqual(readthroughs[0].progress, None)
        self.assertEqual(readthroughs[0].finish_date, None)
        self.assertEqual(delay_mock.call_count, 1)

    def test_create_progress_readthrough(self, delay_mock):
        """a readthrough with progress"""
        self.assertEqual(self.edition.readthrough_set.count(), 0)

        self.client.post(
            "/reading-status/start/{}".format(self.edition.id),
            {
                "start_date": "2020-11-27",
            },
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
        self.assertEqual(delay_mock.call_count, 1)

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
