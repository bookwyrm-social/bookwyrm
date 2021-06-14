""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.connectors import abstract_connector
from bookwyrm.settings import DOMAIN


class Views(TestCase):
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
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        models.Connector.objects.create(
            identifier="self", connector_file="self_connector", local=True
        )
        models.SiteSettings.objects.create()

    def test_search_json_response(self):
        """searches local data only and returns book data in json format"""
        view = views.Search.as_view()
        # we need a connector for this, sorry
        request = self.factory.get("", {"q": "Test Book"})
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = True
            response = view(request)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Test Book")
        self.assertEqual(data[0]["key"], "https://%s/book/%d" % (DOMAIN, self.book.id))

    def test_search_no_query(self):
        """just the search page"""
        view = views.Search.as_view()
        # we need a connector for this, sorry
        request = self.factory.get("")
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = False
            response = view(request)
        self.assertIsInstance(response, TemplateResponse)
        response.render()

    def test_search_books(self):
        """searches remote connectors"""
        view = views.Search.as_view()

        class TestConnector(abstract_connector.AbstractMinimalConnector):
            """nothing added here"""

            def format_search_result(self, search_result):
                pass

            def get_or_create_book(self, remote_id):
                pass

            def parse_search_data(self, data):
                pass

            def format_isbn_search_result(self, search_result):
                return search_result

            def parse_isbn_search_data(self, data):
                return data

        models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
        )
        connector = TestConnector("example.com")

        search_result = abstract_connector.SearchResult(
            key="http://www.example.com/book/1",
            title="Gideon the Ninth",
            author="Tamsyn Muir",
            year="2019",
            connector=connector,
        )

        request = self.factory.get("", {"q": "Test Book", "remote": True})
        request.user = self.local_user
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = False
            with patch("bookwyrm.connectors.connector_manager.search") as manager:
                manager.return_value = [search_result]
                response = view(request)
        self.assertIsInstance(response, TemplateResponse)
        response.render()
        self.assertEqual(response.context_data["results"][0].title, "Gideon the Ninth")

    def test_search_users(self):
        """searches remote connectors"""
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "mouse", "type": "user"})
        request.user = self.local_user
        response = view(request)

        self.assertIsInstance(response, TemplateResponse)
        response.render()
        self.assertEqual(response.context_data["results"][0], self.local_user)

    def test_search_users_logged_out(self):
        """searches remote connectors"""
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "mouse", "type": "user"})

        anonymous_user = AnonymousUser
        anonymous_user.is_authenticated = False
        request.user = anonymous_user

        response = view(request)

        response.render()
        self.assertFalse("results" in response.context_data)

    def test_search_lists(self):
        """searches remote connectors"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            booklist = models.List.objects.create(
                user=self.local_user, name="test list"
            )
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "test", "type": "list"})
        request.user = self.local_user
        response = view(request)

        self.assertIsInstance(response, TemplateResponse)
        response.render()
        self.assertEqual(response.context_data["results"][0], booklist)
