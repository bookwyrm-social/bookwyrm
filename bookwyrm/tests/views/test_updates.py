""" test for app action functionality """
import json
from django.http import JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class UpdateViews(TestCase):
    """ lets the ui check for unread notification """

    def setUp(self):
        """ we need basic test data and mocks """
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_get_updates(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Updates.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["notifications"], 0)

        models.Notification.objects.create(
            notification_type="BOOST", user=self.local_user
        )
        result = view(request)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["notifications"], 1)
