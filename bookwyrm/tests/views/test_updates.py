""" test for app action functionality """
import json
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class UpdateViews(TestCase):
    """lets the ui check for unread notification"""

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
        models.SiteSettings.objects.create()

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

    def test_get_unread_status_count(self):
        """there are so many views, this just makes sure it LOADS"""
        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.activitystreams.ActivityStream.get_unread_count") as mock:
            mock.return_value = 3
            result = views.get_unread_status_count(request, "home")

        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["count"], 3)
