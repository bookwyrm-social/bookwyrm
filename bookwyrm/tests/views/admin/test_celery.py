""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class CeleryStatusViews(TestCase):
    """every response to a get request, html or json"""

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
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        self.local_user.groups.set([group])
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_celery_status_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.CeleryStatus.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
