""" testing import """
import pathlib
from unittest.mock import patch
import datetime
import pytz

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import OpenLibraryImporter
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=pytz.UTC)


# pylint: disable=consider-using-with
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class OpenLibraryImport(TestCase):
    """importing from openlibrary csv"""

    # pylint: disable=invalid-name
    def setUp(self):
        """use a test csv"""
        self.importer = OpenLibraryImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/openlibrary.csv")
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
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

        import_items = (
            models.ImportItem.objects.filter(job=import_job).order_by("index").all()
        )
        self.assertEqual(len(import_items), 4)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["Work Id"], "OL102749W")
        self.assertEqual(import_items[1].data["Work Id"], "OL361393W")
        self.assertEqual(import_items[1].data["Edition Id"], "OL7798182M")

        self.assertEqual(import_items[0].normalized_data["shelf"], "reading")
        self.assertEqual(import_items[0].normalized_data["openlibrary_key"], "")
        self.assertEqual(
            import_items[0].normalized_data["openlibrary_work_key"], "OL102749W"
        )
        self.assertEqual(
            import_items[1].normalized_data["openlibrary_key"], "OL7798182M"
        )
        self.assertEqual(import_items[2].normalized_data["shelf"], "to-read")
        self.assertEqual(import_items[3].normalized_data["shelf"], "read")

    def test_handle_imported_book(self, *_):
        """openlibrary import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READING
        ).first()
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
