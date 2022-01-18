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

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    def test_load_subclass(self, *_):
        """get a status' real type"""
        review = models.Review.objects.create(user=self.user, book=self.book, rating=3)
        status = models.Status.objects.get(id=review.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(bookwyrm_tags.load_subclass(status), models.Review)

        quote = models.Quotation.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=quote.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(bookwyrm_tags.load_subclass(status), models.Quotation)

        comment = models.Comment.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=comment.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(bookwyrm_tags.load_subclass(status), models.Comment)

    def test_related_status(self, *_):
        """gets the subclass model for a notification status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            status = models.Status.objects.create(content="hi", user=self.user)
        notification = models.Notification.objects.create(
            user=self.user, notification_type="MENTION", related_status=status
        )

        result = bookwyrm_tags.related_status(notification)
        self.assertIsInstance(result, models.Status)
