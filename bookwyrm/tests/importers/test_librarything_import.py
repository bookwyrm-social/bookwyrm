""" testing import """
import pathlib
from unittest.mock import patch
import datetime
import pytz

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import LibrarythingImporter
from bookwyrm.importers.importer import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=pytz.UTC)


# pylint: disable=consider-using-with
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class LibrarythingImport(TestCase):
    """importing from librarything tsv"""

    def setUp(self):
        """use a test tsv"""
        self.importer = LibrarythingImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")

        # Librarything generates latin encoded exports...
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mmai", "mmai@mmai.mmai", "password", local=True
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
        self.assertEqual(import_job.user, self.local_user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, "public")

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 3)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["Book Id"], "5498194")
        self.assertEqual(import_items[0].normalized_data["isbn_13"], "9782070291342")
        self.assertEqual(import_items[0].normalized_data["isbn_10"], "2070291340")
        self.assertEqual(import_items[0].normalized_data["title"], "Marelle")
        self.assertEqual(import_items[0].normalized_data["authors"], "Cortazar, Julio")
        self.assertEqual(import_items[0].normalized_data["date_added"], "2006-08-09")
        self.assertEqual(import_items[0].normalized_data["date_started"], "2007-04-16")
        self.assertEqual(import_items[0].normalized_data["date_finished"], "2007-05-08")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data["Book Id"], "5015319")
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].data["Book Id"], "5015399")

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
        self.assertEqual(import_items[0].data["Book Id"], "5498194")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data["Book Id"], "5015319")

    def test_handle_imported_book(self, *_):
        """librarything import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(identifier="read").first()
        self.assertIsNone(shelf.books.first())

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2007, 4, 16))
        self.assertEqual(readthrough.finish_date, make_date(2007, 5, 8))

    def test_handle_imported_book_already_shelved(self, *_):
        """librarything import added a book, this adds related connections"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = self.local_user.shelf_set.filter(identifier="to-read").first()
            models.ShelfBook.objects.create(
                shelf=shelf, user=self.local_user, book=self.book
            )

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertIsNone(
            self.local_user.shelf_set.get(identifier="read").books.first()
        )

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2007, 4, 16))
        self.assertEqual(readthrough.finish_date, make_date(2007, 5, 8))

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_review(self, *_):
        """librarything review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=0).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.content, "chef d'oeuvre")
        self.assertEqual(review.rating, 4.5)
        self.assertEqual(review.published_date, make_date(2007, 5, 8))
        self.assertEqual(review.privacy, "unlisted")
