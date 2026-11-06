"""Tests for landing/about page template tags"""

from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import landing_page_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class LandingPageTags(TestCase):
    """Tests for get_book_superlatives"""

    @classmethod
    def setUpTestData(cls):
        """Create test users, works, and editions"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user_one = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
            )
            cls.user_two = models.User.objects.create_user(
                "vole@example.com",
                "vole@vole.vole",
                "voleword",
                local=True,
                localname="vole",
            )
            cls.user_three = models.User.objects.create_user(
                "shrew@example.com",
                "shrew@shrew.shrew",
                "shrewword",
                local=True,
                localname="shrew",
            )

        cls.single_user_work = models.Work.objects.create(title="Single User Work")
        cls.single_user_book = models.Edition.objects.create(
            title="Single User Book",
            parent_work=cls.single_user_work,
        )

        cls.multi_user_work = models.Work.objects.create(title="Multi User Work")
        cls.multi_user_book = models.Edition.objects.create(
            title="Multi User Book",
            parent_work=cls.multi_user_work,
        )

    def test_top_rated_excludes_single_user_with_multiple_ratings(self, *_):
        """A book rated many times by only one user should not be top_rated"""
        for _ in range(5):
            models.ReviewRating.objects.create(
                user=self.user_one,
                book=self.single_user_book,
                rating=5,
            )

        superlatives = landing_page_tags.get_book_superlatives()
        self.assertIsNone(superlatives["top_rated"])

        models.ReviewRating.objects.create(
            user=self.user_one,
            book=self.multi_user_book,
            rating=4.5,
        )
        models.ReviewRating.objects.create(
            user=self.user_two,
            book=self.multi_user_book,
            rating=4.5,
        )

        superlatives = landing_page_tags.get_book_superlatives()
        self.assertEqual(superlatives["top_rated"], self.multi_user_work)

    def test_top_rated_dedupes_ratings_by_user(self, *_):
        """Duplicate ratings from one user should not outweigh ratings from more users"""
        # single_user_work has 2 distinct users, but user_one rated it 5 times
        for _ in range(5):
            models.ReviewRating.objects.create(
                user=self.user_one,
                book=self.single_user_book,
                rating=5,
            )
        models.ReviewRating.objects.create(
            user=self.user_two,
            book=self.single_user_book,
            rating=5,
        )

        # multi_user_work has 3 distinct users each rating it once
        for user in (self.user_one, self.user_two, self.user_three):
            models.ReviewRating.objects.create(
                user=user,
                book=self.multi_user_book,
                rating=5,
            )

        superlatives = landing_page_tags.get_book_superlatives()
        self.assertEqual(superlatives["top_rated"], self.multi_user_work)
        self.assertEqual(superlatives["top_rated"].rating_count, 3)
