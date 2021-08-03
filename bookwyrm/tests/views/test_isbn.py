""" test for app action functionality """
import json
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.settings import DOMAIN


class IsbnViews(TestCase):
    """tag views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
            remote_id="https://example.com/users/mouse",
        )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Test Book",
            isbn_13="1234567890123",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        models.Connector.objects.create(
            identifier="self", connector_file="self_connector", local=True
        )
        models.SiteSettings.objects.create()

    def test_isbn_json_response(self):
        """searches local data only and returns book data in json format"""
        view = views.Isbn.as_view()
        request = self.factory.get("")
        with patch("bookwyrm.views.isbn.is_api_request") as is_api:
            is_api.return_value = True
            response = view(request, isbn="1234567890123")
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Test Book")
        self.assertEqual(data[0]["key"], "https://%s/book/%d" % (DOMAIN, self.book.id))
