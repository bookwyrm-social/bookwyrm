""" testing import """
from unittest.mock import patch
from django.test import RequestFactory, TestCase

from bookwyrm import models
from bookwyrm.views import rss_feed


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
@patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
@patch("bookwyrm.activitystreams.add_status_task.delay")
class RssFeedView(TestCase):
    """rss feed behaves as expected"""

    def setUp(self):
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "rss_user", "rss@test.rss", "password", local=True
            )
        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        self.factory = RequestFactory()

        models.SiteSettings.objects.create()

    def test_rss_empty(self, *_):
        """load an rss feed"""
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Status updates from rss_user", result.content)

    def test_rss_comment(self, *_):
        """load an rss feed"""
        models.Comment.objects.create(
            content="comment test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Example Edition", result.content)

    def test_rss_review(self, *_):
        """load an rss feed"""
        models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3,
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

    def test_rss_quotation(self, *_):
        """load an rss feed"""
        models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

        self.assertIn(b"a sickening sense", result.content)
