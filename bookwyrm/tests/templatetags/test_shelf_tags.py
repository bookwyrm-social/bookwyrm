""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm.templatetags import shelf_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class ShelfTags(TestCase):
    """lotta different things here"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """create some filler objects"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
            )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                remote_id="http://example.com/rat",
                local=False,
            )
        self.book = models.Edition.objects.create(
            title="Test Book",
            parent_work=models.Work.objects.create(title="Test work"),
        )

    def setUp(self):
        """test data"""
        self.factory = RequestFactory()

    def test_get_is_book_on_shelf(self, *_):
        """check if a book is on a shelf"""
        shelf = self.local_user.shelf_set.first()
        self.assertFalse(shelf_tags.get_is_book_on_shelf(self.book, shelf))
        models.ShelfBook.objects.create(
            shelf=shelf, book=self.book, user=self.local_user
        )
        self.assertTrue(shelf_tags.get_is_book_on_shelf(self.book, shelf))

    def test_get_next_shelf(self, *_):
        """self progress helper"""
        self.assertEqual(shelf_tags.get_next_shelf("to-read"), "reading")
        self.assertEqual(shelf_tags.get_next_shelf("reading"), "read")
        self.assertEqual(shelf_tags.get_next_shelf("read"), "complete")
        self.assertEqual(shelf_tags.get_next_shelf("blooooga"), "to-read")

    def test_active_shelf(self, *_):
        """get the shelf a book is on"""
        shelf = self.local_user.shelf_set.first()
        request = self.factory.get("")
        request.user = self.local_user
        context = {"request": request}
        self.assertIsInstance(shelf_tags.active_shelf(context, self.book), dict)
        models.ShelfBook.objects.create(
            shelf=shelf, book=self.book, user=self.local_user
        )
        self.assertEqual(shelf_tags.active_shelf(context, self.book).shelf, shelf)
