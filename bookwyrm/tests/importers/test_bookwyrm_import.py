""" testing bookwyrm csv import """
import pathlib
from unittest.mock import patch
import datetime

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import BookwyrmBooksImporter
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class BookwyrmBooksImport(TestCase):
    """importing from BookWyrm csv"""

    def setUp(self):
        """use a test csv"""
        self.importer = BookwyrmBooksImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/bookwyrm.csv")
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
                "mouse", "mouse@mouse.mouse", "password", local=True
            )
        models.SiteSettings.objects.create()
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
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
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")
        )
        self.assertEqual(len(import_items), 3)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].normalized_data["isbn_13"], "")
        self.assertEqual(import_items[0].normalized_data["isbn_10"], "")
        self.assertEqual(import_items[0].shelf_name, "To Read")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].normalized_data["isbn_13"], "9780449017036")
        self.assertEqual(import_items[1].normalized_data["isbn_10"], "0449017036")
        self.assertEqual(import_items[1].shelf_name, "Cooking")

        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].normalized_data["isbn_13"], "9780375503122")
        self.assertEqual(import_items[2].normalized_data["isbn_10"], "0375503129")
        self.assertEqual(import_items[2].shelf_name, "Read")

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
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(retry_items[0].data["title"], "我穿我自己")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data["author_text"], "Yotam Ottolenghi")

    def test_handle_imported_book(self, *_):
        """import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
        ).first()
        self.assertIsNone(shelf.books.first())

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.last()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(
            shelf.shelfbook_set.first().shelved_date, make_date(2024, 8, 10)
        )

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2001, 6, 1))
        self.assertEqual(readthrough.finish_date, make_date(2001, 7, 10))

    def test_create_new_shelf(self, *_):
        """import added a book, was a new shelf created?"""
        shelf = self.local_user.shelf_set.filter(identifier="cooking").first()
        self.assertIsNone(shelf)

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")[1]
        )
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        shelf_after = self.local_user.shelf_set.filter(identifier="cooking-9").first()
        self.assertEqual(shelf_after.books.first(), self.book)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_review(self, *_):
        """review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.get(index=1)
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.name, "Too much tahini")
        self.assertEqual(review.content, "...in his hummus")
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.published_date, make_date(2022, 11, 10))
        self.assertEqual(review.privacy, "unlisted")

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_rating(self, *_):
        """rating import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "followers"
        )
        import_item = import_job.items.filter(index=2).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.published_date, make_date(2001, 7, 10))
        self.assertEqual(review.privacy, "followers")
