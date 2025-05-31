""" testing import """
import pathlib
from unittest.mock import patch
import datetime

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import OpenReadsImporter
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class OpenReadsImport(TestCase):
    """importing from openreads csv"""

    def setUp(self):
        """use a test tsv"""
        self.importer = OpenReadsImporter()
        datafile = pathlib.Path(__file__).parent.joinpath(
            "../data/openreads-csv-example.csv"
        )

        # pylint: disable-next=consider-using-with
        self.csv = open(datafile, "r", encoding=self.importer.encoding)

    def tearDown(self):
        """close test csv"""
        self.csv.close()

    @classmethod
    def setUpTestData(cls):
        """populate database"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mmai", "mmai@mmai.mmai", "password", local=True
            )
        models.SiteSettings.objects.create()
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Permanent Record",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_create_job(self, *_):
        """creates the import job entry and checks csv"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        self.assertEqual(import_job.user, self.local_user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, "public")

        import_items = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")
        )
        self.assertEqual(len(import_items), 4)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].normalized_data["isbn_13"], None)
        self.assertEqual(import_items[0].normalized_data["isbn_10"], "")
        self.assertEqual(
            import_items[0].normalized_data["title"], "Wild Flowers Electric Beasts"
        )
        self.assertEqual(import_items[0].normalized_data["authors"], "Alina Leonova")
        self.assertEqual(import_items[0].normalized_data["date_added"], "2024-03-01")
        self.assertEqual(import_items[0].normalized_data["date_started"], None)
        self.assertEqual(import_items[0].normalized_data["date_finished"], None)
        self.assertEqual(import_items[0].normalized_data["shelf"], "to-read")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].normalized_data["title"], "Permanent Record")
        self.assertEqual(import_items[1].normalized_data["date_started"], "2023-10-27")
        self.assertEqual(import_items[1].normalized_data["date_finished"], "2023-11-28")
        self.assertEqual(import_items[1].normalized_data["shelf"], "read")
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].normalized_data["title"], "The Divide")
        self.assertEqual(import_items[2].normalized_data["date_started"], None)
        self.assertEqual(import_items[2].normalized_data["date_finished"], "2023-12-10")
        self.assertEqual(import_items[2].normalized_data["shelf"], "read")
        self.assertEqual(import_items[3].index, 3)
        self.assertEqual(import_items[3].normalized_data["title"], "The road to winter")
        self.assertEqual(import_items[3].normalized_data["date_started"], "2023-10-12")
        self.assertEqual(import_items[3].normalized_data["date_finished"], "2023-11-15")
        self.assertEqual(import_items[3].normalized_data["shelf"], "read")

    def test_create_retry_job(self, *_):
        """trying again with items that didn't import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_items = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")[:2]
        )

        retry = self.importer.create_retry_job(
            self.local_user, import_job, import_items
        )
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.local_user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, "unlisted")

        retry_items = models.ImportItem.objects.filter(job=retry).all().order_by("id")
        self.assertEqual(len(retry_items), 2)
        self.assertEqual(retry_items[0].data["title"], "Wild Flowers Electric Beasts")
        self.assertEqual(retry_items[1].data["title"], "Permanent Record")

    def test_handle_imported_book(self, *_):
        """openreads import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
        ).first()
        self.assertIsNone(shelf.books.first())

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2023, 10, 27))
        self.assertEqual(readthrough.finish_date, make_date(2023, 11, 28))

    def test_handle_imported_book_already_shelved(self, *_):
        """openreads import added a book, this adds related connections"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = self.local_user.shelf_set.filter(
                identifier=models.Shelf.TO_READ
            ).first()
            models.ShelfBook.objects.create(
                shelf=shelf, user=self.local_user, book=self.book
            )

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertIsNone(
            self.local_user.shelf_set.get(
                identifier=models.Shelf.READ_FINISHED
            ).books.first()
        )

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2023, 10, 27))
        self.assertEqual(readthrough.finish_date, make_date(2023, 11, 28))

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_review(self, *_):
        """openreads review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=3).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.published_date, make_date(2023, 11, 15))
        self.assertEqual(review.privacy, "unlisted")
