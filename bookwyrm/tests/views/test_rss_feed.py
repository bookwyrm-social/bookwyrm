""" testing import """

from unittest.mock import patch
from django.test import RequestFactory, TestCase

from bookwyrm import models
from bookwyrm.views import rss_feed


class RssFeedView(TestCase):
    """rss feed behaves as expected"""

    def setUp(self):
        """test data"""
        self.site = models.SiteSettings.objects.create()

        self.user = models.User.objects.create_user(
            "rss_user", "rss@test.rss", "password", local=True
        )

        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
                self.review = models.Review.objects.create(
                    name="Review name",
                    content="test content",
                    rating=3,
                    user=self.user,
                    book=self.book,
                )

                self.quote = models.Quotation.objects.create(
                    quote="a sickening sense",
                    content="test content",
                    user=self.user,
                    book=self.book,
                )

                self.generatednote = models.GeneratedNote.objects.create(
                    content="test content", user=self.user
                )

        self.factory = RequestFactory()

    @patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
    def test_rss_feed(self, _):
        """load an rss feed"""
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.user
        with patch("bookwyrm.models.SiteSettings.objects.get") as site:
            site.return_value = self.site
            result = view(request, username=self.user.username)
        self.assertEqual(result.status_code, 200)

        self.assertIn(b"Status updates from rss_user", result.content)
        self.assertIn(b"a sickening sense", result.content)
        self.assertIn(b"Example Edition", result.content)
