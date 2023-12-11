""" test for app action functionality """
import json
from unittest.mock import patch

from django.http import Http404, JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class UpdateViews(TestCase):
    """lets the ui check for unread notification"""

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
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_get_notification_count(self):
        """there are so many views, this just makes sure it LOADS"""
        request = self.factory.get("")
        request.user = self.local_user

        result = views.get_notification_count(request)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["count"], 0)

        models.Notification.objects.create(
            notification_type="BOOST", user=self.local_user
        )
        result = views.get_notification_count(request)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["count"], 1)

    def test_get_unread_status_string(self):
        """there are so many views, this just makes sure it LOADS"""
        request = self.factory.get("")
        request.user = self.local_user

        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_unread_count"
        ) as mock_count, patch(
            "bookwyrm.activitystreams.ActivityStream.get_unread_count_by_status_type"
        ) as mock_count_by_status:
            mock_count.return_value = 3
            mock_count_by_status.return_value = {"review": 5}
            result = views.get_unread_status_string(request, "home")

        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["count"], "Load 5 unread statuses")

    def test_get_unread_status_string_with_filters(self):
        """there are so many views, this just makes sure it LOADS"""
        self.local_user.feed_status_types = ["comment", "everything"]
        request = self.factory.get("")
        request.user = self.local_user

        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_unread_count"
        ) as mock_count, patch(
            "bookwyrm.activitystreams.ActivityStream.get_unread_count_by_status_type"
        ) as mock_count_by_status:
            mock_count.return_value = 3
            mock_count_by_status.return_value = {
                "generated_note": 1,
                "comment": 1,
                "review": 10,
            }
            result = views.get_unread_status_string(request, "home")

        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["count"], "Load 2 unread statuses")

    def test_get_unread_status_string_invalid_stream(self):
        """there are so many views, this just makes sure it LOADS"""
        request = self.factory.get("")
        request.user = self.local_user

        with self.assertRaises(Http404):
            views.get_unread_status_string(request, "fish")
