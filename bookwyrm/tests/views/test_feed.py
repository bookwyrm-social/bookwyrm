""" test for app action functionality """
from io import BytesIO
from unittest.mock import patch
import pathlib

from PIL import Image
from django.core.files.base import ContentFile
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
@patch("bookwyrm.suggested_users.remove_user_task.delay")
class FeedViews(TestCase):
    """activity feed, statuses, dms"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
            self.another_user = models.User.objects.create_user(
                "nutria@local.com",
                "nutria@nutria.nutria",
                "password",
                local=True,
                localname="nutria",
            )
        self.book = models.Edition.objects.create(
            parent_work=models.Work.objects.create(title="hi"),
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    def test_feed(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Feed.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "home")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    def test_save_feed_settings(self, *_):
        """update display preferences"""
        self.assertEqual(
            self.local_user.feed_status_types,
            ["review", "comment", "quotation", "everything"],
        )
        view = views.Feed.as_view()
        form = forms.FeedStatusTypesForm(instance=self.local_user)
        form.data["feed_status_types"] = "review"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request, "home")

        self.assertEqual(result.status_code, 200)
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.feed_status_types, ["review"])

    def test_status_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
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
            with self.assertRaises(Http404):
                view(request, "mouse", 12345)

    def test_status_page_not_found_wrong_user(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()
        another_user = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.rat",
            "password",
            local=True,
            localname="rat",
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            status = models.Status.objects.create(content="hi", user=another_user)

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "mouse", status.id)

    def test_status_page_with_image(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()

        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
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
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_replies_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Replies.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
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
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_direct_messages_page_user(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DirectMessage.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "nutria")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["partner"], self.another_user)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
    def test_get_suggested_book(self, *_):
        """gets books the ~*~ algorithm ~*~ thinks you want to post about"""
        models.ShelfBook.objects.create(
            book=self.book,
            user=self.local_user,
            shelf=self.local_user.shelf_set.get(identifier="reading"),
        )
        suggestions = views.feed.get_suggested_books(self.local_user)
        self.assertEqual(suggestions[0]["name"], "Currently Reading")
        self.assertEqual(suggestions[0]["books"][0], self.book)
