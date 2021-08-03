""" test for app action functionality """
from io import BytesIO
from unittest.mock import patch
import pathlib

from PIL import Image
from django.core.files.base import ContentFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views
from bookwyrm.activitypub import ActivitypubResponse


@patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class FeedViews(TestCase):
    """activity feed, statuses, dms"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        self.book = models.Edition.objects.create(
            parent_work=models.Work.objects.create(title="hi"),
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.SiteSettings.objects.create()

    def test_feed(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Feed.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "local")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_status_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_status_page_not_found(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", 12345)

        self.assertEqual(result.status_code, 404)

    def test_status_page_with_image(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()

        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Review.objects.create(
                content="hi",
                user=self.local_user,
                book=self.book,
            )
            attachment = models.Image.objects.create(
                status=status, caption="alt text here"
            )
            attachment.image.save("test.jpg", ContentFile(output.getvalue()))

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_replies_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Replies.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_direct_messages_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DirectMessage.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_get_suggested_book(self, *_):
        """gets books the ~*~ algorithm ~*~ thinks you want to post about"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ShelfBook.objects.create(
                book=self.book,
                user=self.local_user,
                shelf=self.local_user.shelf_set.get(identifier="reading"),
            )
        suggestions = views.feed.get_suggested_books(self.local_user)
        self.assertEqual(suggestions[0]["name"], "Currently Reading")
        self.assertEqual(suggestions[0]["books"][0], self.book)
