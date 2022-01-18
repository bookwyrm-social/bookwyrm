""" Gettings book ratings """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import bookwyrm_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class RatingTags(TestCase):
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

    def test_get_user_rating(self, *_):
        """get a user's most recent rating of a book"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.Review.objects.create(user=self.user, book=self.book, rating=3)
        self.assertEqual(bookwyrm_tags.get_user_rating(self.book, self.user), 3)

    def test_get_user_rating_doesnt_exist(self, *_):
        """there is no rating available"""
        self.assertEqual(bookwyrm_tags.get_user_rating(self.book, self.user), 0)
