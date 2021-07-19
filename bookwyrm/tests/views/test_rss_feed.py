""" testing import """
from unittest.mock import patch
from django.test import RequestFactory, TestCase

from bookwyrm import models
from bookwyrm.views import rss_feed


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
@patch("bookwyrm.preview_images.generate_site_preview_image_task.delay")
@patch("bookwyrm.preview_images.generate_user_preview_image_task.delay")
@patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay")
@patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class RssFeedView(TestCase):
    """rss feed behaves as expected"""

    def test_rss_feed(self, *_):
        """load an rss feed"""
        models.SiteSettings.objects.create()

        user = models.User.objects.create_user(
            "rss_user", "rss@test.rss", "password", local=True
        )

        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

        models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3,
            user=user,
            book=book,
        )

        models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=user,
            book=book,
        )

        models.ReadStatus.objects.create(content="test content", user=user)

        factory = RequestFactory()

        view = rss_feed.RssFeed()
        request = factory.get("/user/rss_user/rss")
        request.user = user

        result = view(request, username=user.username)
        self.assertEqual(result.status_code, 200)

        self.assertIn(b"Status updates from rss_user", result.content)
        self.assertIn(b"a sickening sense", result.content)
        self.assertIn(b"Example Edition", result.content)
