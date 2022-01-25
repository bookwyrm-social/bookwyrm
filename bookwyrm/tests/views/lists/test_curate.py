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
    """list view"""

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
        work = models.Work.objects.create(title="Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

        models.SiteSettings.objects.create()

    def test_curate_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Curate.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
                order=1,
            )

        result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)

    def test_curate_approve(self):
        """approve a pending item"""
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
                order=1,
            )

        request = self.factory.post(
            "",
            {"item": pending.id, "approved": "true"},
        )
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            view(request, self.list.id)

        self.assertEqual(mock.call_count, 2)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Add")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["target"], self.list.remote_id)

        pending.refresh_from_db()
        self.assertEqual(self.list.books.count(), 1)
        self.assertEqual(self.list.listitem_set.first(), pending)
        self.assertTrue(pending.approved)

    def test_curate_reject(self):
        """approve a pending item"""
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
                order=1,
            )

        request = self.factory.post(
            "",
            {
                "item": pending.id,
                "approved": "false",
            },
        )
        request.user = self.local_user

        view(request, self.list.id)

        self.assertFalse(self.list.books.exists())
        self.assertFalse(models.ListItem.objects.exists())
