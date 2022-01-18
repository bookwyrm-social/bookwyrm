""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import bookwyrm_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class BookWyrmTags(TestCase):
    """lotta different things here"""

    def setUp(self):
        """create some filler objects"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
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
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_book_description(self, *_):
        """grab it from the edition or the parent"""
        work = models.Work.objects.create(title="Test Work")
        self.book.parent_work = work
        self.book.save()

        self.assertIsNone(bookwyrm_tags.get_book_description(self.book))

        work.description = "hi"
        work.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), "hi")

        self.book.description = "hello"
        self.book.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), "hello")
