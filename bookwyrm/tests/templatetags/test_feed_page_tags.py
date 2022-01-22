""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import feed_page_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class FeedPageTags(TestCase):
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

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    def test_load_subclass(self, *_):
        """get a status' real type"""
        review = models.Review.objects.create(user=self.user, book=self.book, rating=3)
        status = models.Status.objects.get(id=review.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Review)

        quote = models.Quotation.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=quote.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Quotation)

        comment = models.Comment.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=comment.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Comment)
