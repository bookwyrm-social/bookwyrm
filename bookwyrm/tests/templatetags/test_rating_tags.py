""" Gettings book ratings """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import rating_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class RatingTags(TestCase):
    """lotta different things here"""

    @classmethod
    def setUpTestData(cls):
        """create some filler objects"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
            )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                remote_id="http://example.com/rat",
                local=False,
            )
        work = models.Work.objects.create(title="Work title")
        cls.book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    def test_get_rating(self, *_):
        """privacy filtered rating. Commented versions are how it ought to work with
        subjective ratings, which are currently not used for performance reasons."""
        # follows-only: not included
        models.ReviewRating.objects.create(
            user=self.remote_user,
            rating=5,
            book=self.book,
            privacy="followers",
        )
        # self.assertEqual(rating_tags.get_rating(self.book, self.local_user), 0)
        self.assertEqual(rating_tags.get_rating(self.book, self.local_user), 5)

        # public: included
        models.ReviewRating.objects.create(
            user=self.remote_user,
            rating=5,
            book=self.book,
            privacy="public",
        )
        self.assertEqual(rating_tags.get_rating(self.book, self.local_user), 5)

        # rating unset: not included
        models.Review.objects.create(
            name="blah",
            user=self.local_user,
            rating=0,
            book=self.book,
            privacy="public",
        )
        self.assertEqual(rating_tags.get_rating(self.book, self.local_user), 5)

    def test_get_rating_broken_edition(self, *_):
        """Don't have a server error if an edition is missing a work"""
        broken_book = models.Edition.objects.create(title="Test")
        broken_book.parent_work = None
        self.assertIsNone(rating_tags.get_rating(broken_book, self.local_user))

    def test_get_user_rating(self, *_):
        """get a user's most recent rating of a book"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.Review.objects.create(user=self.local_user, book=self.book, rating=3)
        self.assertEqual(rating_tags.get_user_rating(self.book, self.local_user), 3)

    def test_get_user_rating_doesnt_exist(self, *_):
        """there is no rating available"""
        self.assertEqual(rating_tags.get_user_rating(self.book, self.local_user), 0)
