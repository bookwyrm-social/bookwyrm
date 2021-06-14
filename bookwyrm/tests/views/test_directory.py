""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views

# pylint: disable=unused-argument
class DirectoryViews(TestCase):
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
        self.rat = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
            discoverable=True,
        )
        models.SiteSettings.objects.create()

    def test_directory_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Directory.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
