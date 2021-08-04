""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class UserViews(TestCase):
    """view user and edit profile"""

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
        models.User.objects.create_user(
            "rat@local.com", "rat@rat.rat", "password", local=True, localname="rat"
        )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            models.User.objects.create_user(
                "rat",
                "rat@remote.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        models.SiteSettings.objects.create()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_webfinger(self):
        """there are so many views, this just makes sure it LOADS"""
        request = self.factory.get("", {"resource": "acct:mouse@local.com"})
        request.user = self.anonymous_user

        result = views.webfinger(request)
        self.assertIsInstance(result, JsonResponse)
        data = json.loads(result.getvalue())
        self.assertEqual(data["subject"], "acct:mouse@local.com")

    def test_nodeinfo_pointer(self):
        """just tells you where nodeinfo is"""
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = views.nodeinfo_pointer(request)
        data = json.loads(result.getvalue())
        self.assertIsInstance(result, JsonResponse)
        self.assertTrue("href" in data["links"][0])

    def test_nodeinfo(self):
        """info about the instance"""
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = views.nodeinfo(request)
        data = json.loads(result.getvalue())
        self.assertIsInstance(result, JsonResponse)
        self.assertEqual(data["software"]["name"], "bookwyrm")
        self.assertEqual(data["usage"]["users"]["total"], 2)
        self.assertEqual(models.User.objects.count(), 3)

    def test_instanceinfo(self):
        """about the instance's user activity"""
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = views.instance_info(request)
        data = json.loads(result.getvalue())
        self.assertIsInstance(result, JsonResponse)
        self.assertEqual(data["stats"]["user_count"], 2)
        self.assertEqual(models.User.objects.count(), 3)
