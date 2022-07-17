""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.book_search import SearchResult
from bookwyrm.settings import DOMAIN
from bookwyrm.tests.validate_html import validate_html


class Views(TestCase):
    """tag views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
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
        models.SiteSettings.objects.create()

    def test_search_json_response(self):
        """searches local data only and returns book data in json format"""
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "Test Book"})
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = True
            response = view(request)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Test Book")
        self.assertEqual(data[0]["key"], f"https://{DOMAIN}/book/{self.book.id}")

    def test_search_no_query(self):
        """just the search page"""
        view = views.Search.as_view()
        # we need a connector for this, sorry
        request = self.factory.get("")
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = False
            response = view(request)
        self.assertIsInstance(response, TemplateResponse)
        validate_html(response.render())

    def test_search_books(self):
        """searches remote connectors"""
        view = views.Search.as_view()

        connector = models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
        )
        mock_result = SearchResult(title="Mock Book", connector=connector, key="hello")

        request = self.factory.get("", {"q": "Test Book", "remote": True})
        request.user = self.local_user
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = False
            with patch("bookwyrm.connectors.connector_manager.search") as remote_search:
                remote_search.return_value = [
                    {"results": [mock_result], "connector": connector}
                ]
                response = view(request)

        self.assertIsInstance(response, TemplateResponse)
        validate_html(response.render())
        connector_results = response.context_data["results"]
        self.assertEqual(len(connector_results), 2)
        self.assertEqual(connector_results[0]["results"][0].title, "Test Book")
        self.assertEqual(connector_results[1]["results"][0].title, "Mock Book")

        # don't search remote
        request = self.factory.get("", {"q": "Test Book", "remote": True})
        anonymous_user = AnonymousUser
        anonymous_user.is_authenticated = False
        request.user = anonymous_user
        with patch("bookwyrm.views.search.is_api_request") as is_api:
            is_api.return_value = False
            with patch("bookwyrm.connectors.connector_manager.search") as remote_search:
                remote_search.return_value = [
                    {"results": [mock_result], "connector": connector}
                ]
                response = view(request)
        self.assertIsInstance(response, TemplateResponse)
        validate_html(response.render())
        connector_results = response.context_data["results"]
        self.assertEqual(len(connector_results), 1)
        self.assertEqual(connector_results[0]["results"][0].title, "Test Book")

    def test_search_users(self):
        """searches remote connectors"""
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "mouse", "type": "user"})
        request.user = self.local_user
        response = view(request)

        self.assertIsInstance(response, TemplateResponse)
        validate_html(response.render())
        self.assertEqual(response.context_data["results"][0], self.local_user)

    def test_search_users_logged_out(self):
        """searches remote connectors"""
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "mouse", "type": "user"})

        anonymous_user = AnonymousUser
        anonymous_user.is_authenticated = False
        request.user = anonymous_user

        response = view(request)

        validate_html(response.render())
        self.assertFalse("results" in response.context_data)

    def test_search_lists(self):
        """searches remote connectors"""
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.lists_stream.remove_list_task.delay"):
            booklist = models.List.objects.create(
                user=self.local_user, name="test list"
            )
        view = views.Search.as_view()
        request = self.factory.get("", {"q": "test", "type": "list"})
        request.user = self.local_user
        response = view(request)

        self.assertIsInstance(response, TemplateResponse)
        validate_html(response.render())
        self.assertEqual(response.context_data["results"][0], booklist)
