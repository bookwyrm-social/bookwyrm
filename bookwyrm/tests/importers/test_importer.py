""" testing import """
from collections import namedtuple
import pathlib
from unittest.mock import patch
import datetime
import pytz

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.importers import Importer
from bookwyrm.models.import_job import start_import_task, import_item_task
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=pytz.UTC)


# pylint: disable=consider-using-with
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class GenericImporter(TestCase):
    """importing from csv"""

    # pylint: disable=invalid-name
    def setUp(self):
        """use a test csv"""

        self.importer = Importer()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/generic.csv")
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
            )
        models.SiteSettings.objects.create()
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
        self.assertEqual(len(import_items), 4)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].normalized_data["id"], "38")
        self.assertEqual(import_items[0].normalized_data["title"], "Gideon the Ninth")
        self.assertEqual(import_items[0].normalized_data["authors"], "Tamsyn Muir")
        self.assertEqual(import_items[0].normalized_data["isbn_13"], "9781250313195")
        self.assertIsNone(import_items[0].normalized_data["isbn_10"])
        self.assertEqual(import_items[0].normalized_data["shelf"], "read")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].normalized_data["id"], "48")
        self.assertEqual(import_items[1].normalized_data["title"], "Harrow the Ninth")

        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].normalized_data["id"], "23")
        self.assertEqual(import_items[2].normalized_data["title"], "Subcutanean")

        self.assertEqual(import_items[3].index, 3)
        self.assertEqual(import_items[3].normalized_data["id"], "10")
        self.assertEqual(import_items[3].normalized_data["title"], "Patisserie at Home")

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
        self.assertEqual(retry_items[0].normalized_data["id"], "38")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].normalized_data["id"], "48")

    def test_start_import(self, *_):
        """check that a task was created"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        MockTask = namedtuple("Task", ("id"))
        with patch("bookwyrm.models.import_job.start_import_task.delay") as mock:
            mock.return_value = MockTask(123)
            import_job.start_job()
        self.assertEqual(mock.call_count, 1)
        import_job.refresh_from_db()
        self.assertEqual(import_job.task_id, "123")

    @responses.activate
    def test_start_import_task(self, *_):
        """resolve entry"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )

        MockTask = namedtuple("Task", ("id"))
        with patch("bookwyrm.models.import_job.import_item_task.delay") as mock:
            mock.return_value = MockTask(123)
            start_import_task(import_job.id)

        self.assertEqual(mock.call_count, 4)

    @responses.activate
    def test_import_item_task(self, *_):
        """resolve entry"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )

        import_item = models.ImportItem.objects.get(job=import_job, index=0)
        with patch(
            "bookwyrm.models.import_job.ImportItem.get_book_from_identifier"
        ) as resolve:
            resolve.return_value = self.book

            with patch(
                "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
            ) as mock:
                import_item_task(import_item.id)
                kwargs = mock.call_args.kwargs
        self.assertEqual(kwargs["queue"], "import_triggered")
        import_item.refresh_from_db()

    def test_complete_job(self, *_):
        """test notification"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        items = import_job.items.all()
        for item in items[:3]:
            item.fail_reason = "hello"
            item.save()
            item.update_job()
            self.assertFalse(
                models.Notification.objects.filter(
                    user=self.local_user,
                    related_import=import_job,
                    notification_type="IMPORT",
                ).exists()
            )

        item = items.last()
        item.fail_reason = "hello"
        item.save()
        item.update_job()
        import_job.refresh_from_db()
        self.assertTrue(import_job.complete)
        self.assertTrue(
            models.Notification.objects.filter(
                user=self.local_user,
                related_import=import_job,
                notification_type="IMPORT",
            ).exists()
        )

    def test_handle_imported_book(self, *_):
        """import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
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

    def test_handle_imported_book_already_shelved(self, *_):
        """import added a book, this adds related connections"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = self.local_user.shelf_set.filter(
                identifier=models.Shelf.TO_READ
            ).first()
            models.ShelfBook.objects.create(
                shelf=shelf,
                user=self.local_user,
                book=self.book,
                shelved_date=make_date(2020, 2, 2),
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
        self.assertEqual(
            shelf.shelfbook_set.first().shelved_date, make_date(2020, 2, 2)
        )
        self.assertIsNone(
            self.local_user.shelf_set.get(
                identifier=models.Shelf.READ_FINISHED
            ).books.first()
        )

    def test_handle_import_twice(self, *_):
        """re-importing books"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
        ).first()
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)
            handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(models.ReadThrough.objects.count(), 1)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_review(self, *_):
        """review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=3).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            with patch("bookwyrm.models.Status.broadcast") as broadcast_mock:
                handle_imported_book(import_item)
        kwargs = broadcast_mock.call_args.kwargs
        self.assertEqual(kwargs["software"], "bookwyrm")
        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.content, "mixed feelings")
        self.assertEqual(review.rating, 2.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review, review)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_rating(self, *_):
        """rating import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)
        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_rating_duplicate_with_link(self, *_):
        """rating import twice"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)
            handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_handle_imported_book_rating_duplicate_without_link(self, *_):
        """rating import twice"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)
        import_item.refresh_from_db()
        import_item.linked_review = None
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    def test_handle_imported_book_reviews_disabled(self, *_):
        """review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_item = import_job.items.filter(index=3).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            handle_imported_book(import_item)
        self.assertFalse(
            models.Review.objects.filter(book=self.book, user=self.local_user).exists()
        )

    def test_import_limit(self, *_):
        """checks if import limit works"""
        site_settings = models.SiteSettings.objects.get()
        site_settings.import_size_limit = 2
        site_settings.import_limit_reset = 2
        site_settings.save()

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 2)
