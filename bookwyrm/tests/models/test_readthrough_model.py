""" testing models """
from django.test import TestCase
from django.core.exceptions import ValidationError

from bookwyrm import models


class ReadThrough(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """look, a shelf"""
        self.user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )

        self.work = models.Work.objects.create(title="Example Work")

        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )

        self.readthrough = models.ReadThrough.objects.create(
            user=self.user, book=self.edition
        )

    def test_progress_update(self):
        """Test progress updates"""
        self.readthrough.create_update()  # No-op, no progress yet
        self.readthrough.progress = 10
        self.readthrough.create_update()
        self.readthrough.progress = 20
        self.readthrough.progress_mode = models.ProgressMode.PERCENT
        self.readthrough.create_update()

        updates = self.readthrough.progressupdate_set.order_by("created_date").all()
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].progress, 10)
        self.assertEqual(updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(updates[1].progress, 20)
        self.assertEqual(updates[1].mode, models.ProgressMode.PERCENT)

        self.readthrough.progress = -10
        self.assertRaises(ValidationError, self.readthrough.clean_fields)
        update = self.readthrough.create_update()
        self.assertRaises(ValidationError, update.clean_fields)
