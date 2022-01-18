""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import book_display_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class BookDisplayTags(TestCase):
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
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_book_description(self, *_):
        """grab it from the edition or the parent"""
        work = models.Work.objects.create(title="Test Work")
        self.book.parent_work = work
        self.book.save()

        self.assertIsNone(book_display_tags.get_book_description(self.book))

        work.description = "hi"
        work.save()
        self.assertEqual(book_display_tags.get_book_description(self.book), "hi")

        self.book.description = "hello"
        self.book.save()
        self.assertEqual(book_display_tags.get_book_description(self.book), "hello")

    def test_get_book_file_links(self, *_):
        """load approved links"""
        link = models.FileLink.objects.create(
            book=self.book,
            url="https://web.site/hello",
        )
        links = book_display_tags.get_book_file_links(self.book)
        # the link is pending
        self.assertFalse(links.exists())

        domain = link.domain
        domain.status = "approved"
        domain.save()

        links = book_display_tags.get_book_file_links(self.book)
        self.assertTrue(links.exists())
        self.assertEqual(links[0], link)
