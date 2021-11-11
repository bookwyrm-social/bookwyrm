""" testing import """
import csv
import pathlib
from unittest.mock import patch
import datetime
import pytz

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import StorygraphImporter
from bookwyrm.importers.importer import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=pytz.UTC)


# pylint: disable=consider-using-with
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class StorygraphImport(TestCase):
    """importing from storygraph csv"""

    def setUp(self):
        """use a test csv"""
        self.importer = StorygraphImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/storygraph.csv")
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
            )

        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_create_job(self, *_):
        """creates the import job entry and checks csv"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 2)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["Title"], "Always Coming Home")
        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data["Title"], "Subprime Attention Crisis")
        self.assertEqual(import_items[1].data["My Rating"], 5.0)

    def test_create_retry_job(self, *_):
        """trying again with items that didn't import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_items = models.ImportItem.objects.filter(job=import_job).all()[:2]

        retry = self.importer.create_retry_job(
            self.local_user, import_job, import_items
        )
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.local_user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, "unlisted")

        retry_items = models.ImportItem.objects.filter(job=retry).all()
        self.assertEqual(len(retry_items), 2)
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(retry_items[0].data["Title"], "Always Coming Home")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data["Title"], "Subprime Attention Crisis")

    def test_handle_imported_book(self, *_):
        """storygraph import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(identifier="to-read").first()
        self.assertIsNone(shelf.books.first())

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.local_user, import_item, False, "public"
            )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(
            shelf.shelfbook_set.first().shelved_date, make_date(2021, 5, 10)
        )

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_rating(self, *_):
        """storygraph rating import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.local_user, import_item, True, "unlisted"
            )
        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 5.0)
        self.assertEqual(review.published_date, make_date(2021, 5, 10))
        self.assertEqual(review.privacy, "unlisted")
