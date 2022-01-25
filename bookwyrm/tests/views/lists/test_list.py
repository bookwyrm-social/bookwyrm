""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse
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
        work_two = models.Work.objects.create(title="Labori")
        self.book_two = models.Edition.objects.create(
            title="Example Edition 2",
            remote_id="https://example.com/book/2",
            parent_work=work_two,
        )
        work_three = models.Work.objects.create(title="Trabajar")
        self.book_three = models.Edition.objects.create(
            title="Example Edition 3",
            remote_id="https://example.com/book/3",
            parent_work=work_three,
        )
        work_four = models.Work.objects.create(title="Travailler")
        self.book_four = models.Edition.objects.create(
            title="Example Edition 4",
            remote_id="https://example.com/book/4",
            parent_work=work_four,
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

        models.SiteSettings.objects.create()

    def test_list_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user
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
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_list_page_sorted(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            for (i, book) in enumerate([self.book, self.book_two, self.book_three]):
                models.ListItem.objects.create(
                    book_list=self.list,
                    user=self.local_user,
                    book=book,
                    approved=True,
                    order=i + 1,
                )

        request = self.factory.get("/?sort_by=order")
        request.user = self.local_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=title")
        request.user = self.local_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=rating")
        request.user = self.local_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=sdkfh")
        request.user = self.local_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_list_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_list_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_list_page_json_view(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_list_page_json_view_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        request = self.factory.get("/?page=1")
        request.user = self.local_user
        with patch("bookwyrm.views.list.list.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_list_edit(self):
        """edit a list"""
        view = views.List.as_view()
        request = self.factory.post(
            "",
            {
                "name": "New Name",
                "description": "wow",
                "privacy": "direct",
                "curation": "curated",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            result = view(request, self.list.id)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], self.list.remote_id)

        self.assertEqual(result.status_code, 302)

        self.list.refresh_from_db()
        self.assertEqual(self.list.name, "New Name")
        self.assertEqual(self.list.description, "wow")
        self.assertEqual(self.list.privacy, "direct")
        self.assertEqual(self.list.curation, "curated")
