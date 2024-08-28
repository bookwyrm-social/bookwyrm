""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class ListViews(TestCase):
    """list view"""

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
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        work = models.Work.objects.create(title="Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

        with (
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
        ):
            cls.list = models.List.objects.create(name="Test List", user=cls.local_user)

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_embed_call_without_key(self):
        """there are so many views, this just makes sure it DOESN’T load"""
        view = views.unsafe_embed_list
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, self.list.id, "")

    def test_embed_call_with_key(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.unsafe_embed_list
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        embed_key = str(self.list.embed_key.hex)

        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id, embed_key)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
