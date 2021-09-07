""" testing models """
import datetime
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from bookwyrm import models


class ReadThrough(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """look, a shelf"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )

        self.work = models.Work.objects.create(title="Example Work")
        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )

    def test_valid_date(self):
        """can't finish a book before you start it"""
        start = timezone.now()
        finish = start + datetime.timedelta(days=1)
        # just make sure there's no errors
        models.ReadThrough.objects.create(
            user=self.user,
            book=self.edition,
            start_date=start,
            finish_date=finish,
        )

    def test_valid_date_null_start(self):
        """can't finish a book before you start it"""
        start = timezone.now()
        finish = start + datetime.timedelta(days=1)
        # just make sure there's no errors
        models.ReadThrough.objects.create(
            user=self.user,
            book=self.edition,
            finish_date=finish,
        )

    def test_valid_date_null_finish(self):
        """can't finish a book before you start it"""
        start = timezone.now()
        # just make sure there's no errors
        models.ReadThrough.objects.create(
            user=self.user,
            book=self.edition,
            start_date=start,
        )

    def test_valid_date_null(self):
        """can't finish a book before you start it"""
        # just make sure there's no errors
        models.ReadThrough.objects.create(
            user=self.user,
            book=self.edition,
        )

    def test_valid_date_same(self):
        """can't finish a book before you start it"""
        start = timezone.now()
        # just make sure there's no errors
        models.ReadThrough.objects.create(
            user=self.user,
            book=self.edition,
            start_date=start,
            finish_date=start,
        )

    def test_progress_update(self):
        """Test progress updates"""
        readthrough = models.ReadThrough.objects.create(
            user=self.user, book=self.edition
        )

        readthrough.create_update()  # No-op, no progress yet
        readthrough.progress = 10
        readthrough.create_update()
        readthrough.progress = 20
        readthrough.progress_mode = models.ProgressMode.PERCENT
        readthrough.create_update()

        updates = readthrough.progressupdate_set.order_by("created_date").all()
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].progress, 10)
        self.assertEqual(updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(updates[1].progress, 20)
        self.assertEqual(updates[1].mode, models.ProgressMode.PERCENT)

        readthrough.progress = -10
        self.assertRaises(ValidationError, readthrough.clean_fields)
        update = readthrough.create_update()
        self.assertRaises(ValidationError, update.clean_fields)
