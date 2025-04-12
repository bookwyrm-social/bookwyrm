""" test for app action functionality """
from unittest.mock import patch
import pytest

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class ConnectorViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        cls.local_user.groups.set([group])
        models.SiteSettings.objects.create()

        cls.connector = models.Connector.objects.create(
            identifier="bookwyrm.social",
            name="Bookwyrm.social",
            connector_file="bookwyrm_connector",
            base_url="https://bookwyrm.social",
            books_url="https://bookwyrm.social/book",
            covers_url="https://bookwyrm.social/images/",
            search_url="https://bookwyrm.social/search?q=",
            isbn_search_url="https://bookwyrm.social/isbn/",
            priority=2,
        )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_connector_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ConnectorSettings.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_deactivate_connector(self):
        """test deactivating a connector"""

        view = views.deactivate_connector

        request = self.factory.post("")
        request.user = self.local_user

        self.assertTrue(self.connector.active)

        view(request, self.connector.id)
        self.connector.refresh_from_db()

        self.assertFalse(self.connector.active)

    def test_activate_connector(self):
        """test activating a connector"""

        view = views.activate_connector

        request = self.factory.post("")
        request.user = self.local_user

        self.connector.active = False
        self.connector.save()

        view(request, self.connector.id)
        self.connector.refresh_from_db()

        self.assertTrue(self.connector.active)

    def test_set_connector_priority(self):
        """test setting connector priority"""

        view = views.set_connector_priority

        request = self.factory.post("", {"priority": "99"})
        request.user = self.local_user

        self.assertEqual(self.connector.priority, 2)

        view(request, self.connector.id)
        self.connector.refresh_from_db()

        self.assertTrue(self.connector.priority, 99)

    pytest.mark.skip("not in use so can't be tested")

    def test_update_connector(self):
        """test updating connector"""

    def test_create_connector(self):
        """test creating a connector"""

        self.assertFalse(
            models.Connector.objects.filter(connector_file="finna").exists()
        )

        view = views.create_connector

        request = self.factory.post("", {"connector_file": "finna"})
        request.user = self.local_user

        view(request)

        self.assertTrue(
            models.Connector.objects.filter(connector_file="finna").exists()
        )
