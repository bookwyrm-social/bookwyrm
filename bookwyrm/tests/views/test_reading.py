""" test for app action functionality """
from unittest.mock import patch
import dateutil
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import models, views


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class ReadingViews(TestCase):
    """viewing and creating statuses"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )

    def test_start_reading(self, *_):
        """begin a book"""
        shelf = self.local_user.shelf_set.get(identifier=models.Shelf.READING)
        self.assertFalse(shelf.books.exists())
        self.assertFalse(models.Status.objects.exists())

        request = self.factory.post(
            "",
            {
                "post-status": True,
                "privacy": "followers",
                "start_date": "2020-01-05",
                "book": self.book.id,
                "mention_books": self.book.id,
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.ReadingStatus.as_view()(request, "start", self.book.id)

        self.assertEqual(shelf.books.get(), self.book)

        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.get(), self.book)
        self.assertEqual(status.privacy, "followers")

        readthrough = models.ReadThrough.objects.get()
        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNone(readthrough.finish_date)
        self.assertEqual(readthrough.user, self.local_user)
        self.assertEqual(readthrough.book, self.book)

    def test_start_reading_with_comment(self, *_):
        """begin a book"""
        shelf = self.local_user.shelf_set.get(identifier=models.Shelf.READING)
        self.assertFalse(shelf.books.exists())
        self.assertFalse(models.Status.objects.exists())

        request = self.factory.post(
            "",
            {
                "post-status": True,
                "privacy": "followers",
                "start_date": "2020-01-05",
                "content": "hello hello",
                "book": self.book.id,
                "mention_books": self.book.id,
                "user": self.local_user.id,
                "reading_status": "reading",
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.ReadingStatus.as_view()(request, "start", self.book.id)

        self.assertEqual(shelf.books.get(), self.book)

        status = models.Comment.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.book, self.book)
        self.assertFalse(status.mention_books.exists())
        self.assertEqual(status.privacy, "followers")
        self.assertEqual(status.content, "<p>hello hello</p>")
        self.assertEqual(status.reading_status, "reading")

        readthrough = models.ReadThrough.objects.get()
        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNone(readthrough.finish_date)
        self.assertEqual(readthrough.user, self.local_user)
        self.assertEqual(readthrough.book, self.book)

    @patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
    @patch("bookwyrm.activitystreams.remove_book_statuses_task.delay")
    def test_start_reading_reshelve(self, *_):
        """begin a book"""
        to_read_shelf = self.local_user.shelf_set.get(identifier=models.Shelf.TO_READ)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ShelfBook.objects.create(
                shelf=to_read_shelf, book=self.book, user=self.local_user
            )
        shelf = self.local_user.shelf_set.get(identifier="reading")
        self.assertEqual(to_read_shelf.books.get(), self.book)
        self.assertFalse(shelf.books.exists())
        self.assertFalse(models.Status.objects.exists())

        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.ReadingStatus.as_view()(request, "start", self.book.id)

        self.assertFalse(to_read_shelf.books.exists())
        self.assertEqual(shelf.books.get(), self.book)

    def test_finish_reading(self, *_):
        """begin a book"""
        shelf = self.local_user.shelf_set.get(identifier=models.Shelf.READ_FINISHED)
        self.assertFalse(shelf.books.exists())
        self.assertFalse(models.Status.objects.exists())
        readthrough = models.ReadThrough.objects.create(
            user=self.local_user, start_date=timezone.now(), book=self.book
        )

        request = self.factory.post(
            "",
            {
                "post-status": True,
                "privacy": "followers",
                "start_date": readthrough.start_date,
                "finish_date": timezone.now().isoformat(),
                "id": readthrough.id,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.ReadingStatus.as_view()(request, "finish", self.book.id)

        self.assertEqual(shelf.books.get(), self.book)

        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.get(), self.book)
        self.assertEqual(status.privacy, "followers")

        readthrough = models.ReadThrough.objects.get()
        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNotNone(readthrough.finish_date)
        self.assertEqual(readthrough.user, self.local_user)
        self.assertEqual(readthrough.book, self.book)

    def test_edit_readthrough(self, *_):
        """adding dates to an ongoing readthrough"""
        start = timezone.make_aware(dateutil.parser.parse("2021-01-03"))
        readthrough = models.ReadThrough.objects.create(
            book=self.book, user=self.local_user, start_date=start
        )
        request = self.factory.post(
            "",
            {
                "start_date": "2017-01-01",
                "finish_date": "2018-03-07",
                "book": "",
                "id": readthrough.id,
            },
        )
        request.user = self.local_user

        views.edit_readthrough(request)
        readthrough.refresh_from_db()
        self.assertEqual(readthrough.start_date.year, 2017)
        self.assertEqual(readthrough.start_date.month, 1)
        self.assertEqual(readthrough.start_date.day, 1)
        self.assertEqual(readthrough.finish_date.year, 2018)
        self.assertEqual(readthrough.finish_date.month, 3)
        self.assertEqual(readthrough.finish_date.day, 7)
        self.assertEqual(readthrough.book, self.book)

    def test_delete_readthrough(self, *_):
        """remove a readthrough"""
        readthrough = models.ReadThrough.objects.create(
            book=self.book, user=self.local_user
        )
        models.ReadThrough.objects.create(book=self.book, user=self.local_user)
        request = self.factory.post(
            "",
            {
                "id": readthrough.id,
            },
        )
        request.user = self.local_user

        views.delete_readthrough(request)
        self.assertFalse(models.ReadThrough.objects.filter(id=readthrough.id).exists())

    def test_create_readthrough(self, *_):
        """adding new read dates"""
        request = self.factory.post(
            "",
            {
                "start_date": "2017-01-01",
                "finish_date": "2018-03-07",
                "book": self.book.id,
                "id": "",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user

        views.ReadThrough.as_view()(request)
        readthrough = models.ReadThrough.objects.get()
        self.assertEqual(readthrough.start_date.year, 2017)
        self.assertEqual(readthrough.start_date.month, 1)
        self.assertEqual(readthrough.start_date.day, 1)
        self.assertEqual(readthrough.finish_date.year, 2018)
        self.assertEqual(readthrough.finish_date.month, 3)
        self.assertEqual(readthrough.finish_date.day, 7)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.user, self.local_user)

    def test_update_progress_comment(self, *_):
        """update progress with commentary"""
        readthrough = models.ReadThrough.objects.create(
            user=self.local_user, start_date=timezone.now(), book=self.book
        )
        request = self.factory.post(
            "",
            {
                "post-status": True,
                "privacy": "followers",
                "start_date": "2020-01-05",
                "content": "hello hello",
                "book": self.book.id,
                "mention_books": self.book.id,
                "user": self.local_user.id,
                "id": readthrough.id,
                "progress": 23,
                "progress_mode": "PCT",
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.update_progress(request, self.book.id)

        status = models.Comment.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.book, self.book)
        self.assertFalse(status.mention_books.exists())
        self.assertEqual(status.privacy, "followers")
        self.assertEqual(status.content, "<p>hello hello</p>")
        self.assertIsNone(status.reading_status)
        self.assertEqual(status.progress, 23)
        self.assertEqual(status.progress_mode, "PCT")

        self.assertIsNotNone(readthrough.start_date)
        self.assertIsNone(readthrough.finish_date)
        self.assertEqual(readthrough.user, self.local_user)
        self.assertEqual(readthrough.book, self.book)
