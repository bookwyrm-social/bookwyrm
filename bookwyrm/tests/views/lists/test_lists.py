""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html

# pylint: disable=unused-argument
class ListViews(TestCase):
    """lists of lists"""

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
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

        models.SiteSettings.objects.create()

    @patch("bookwyrm.lists_stream.ListsStream.get_list_stream")
    def test_lists_page(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Lists.as_view()
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.lists_stream.add_list_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_saved_lists_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.SavedLists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            booklist = models.List.objects.create(
                name="Public list", user=self.local_user
            )
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        self.local_user.saved_lists.add(booklist)
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["lists"].object_list, [booklist])

    def test_saved_lists_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.SavedLists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["lists"].object_list), 0)

    def test_saved_lists_page_logged_out(self):
        """logged out saved lists"""
        view = views.SavedLists.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request)
        self.assertEqual(result.status_code, 302)

    def test_user_lists_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserLists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_user_lists_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserLists.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, self.local_user.username)
        self.assertEqual(result.status_code, 302)

    def test_lists_create(self):
        """create list view"""
        view = views.Lists.as_view()
        request = self.factory.post(
            "",
            {
                "name": "A list",
                "description": "wow",
                "privacy": "unlisted",
                "curation": "open",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            result = view(request)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Create")
        self.assertEqual(activity["actor"], self.local_user.remote_id)

        self.assertEqual(result.status_code, 302)
        new_list = models.List.objects.filter(name="A list").get()
        self.assertEqual(new_list.description, "wow")
        self.assertEqual(new_list.privacy, "unlisted")
        self.assertEqual(new_list.curation, "open")
