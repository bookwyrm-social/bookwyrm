""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse

# pylint: disable=unused-argument
class ListViews(TestCase):
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

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_lists_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Lists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

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
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            result = view(request)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Create")
        self.assertEqual(activity["actor"], self.local_user.remote_id)

        self.assertEqual(result.status_code, 302)
        new_list = models.List.objects.filter(name="A list").get()
        self.assertEqual(new_list.description, "wow")
        self.assertEqual(new_list.privacy, "unlisted")
        self.assertEqual(new_list.curation, "open")

    def test_list_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_list_page_sorted(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
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
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=title")
        request.user = self.local_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=rating")
        request.user = self.local_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?sort_by=sdkfh")
        request.user = self.local_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_list_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_list_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_list_page_json_view(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )

        with patch("bookwyrm.views.list.is_api_request") as is_api:
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
        with patch("bookwyrm.views.list.is_api_request") as is_api:
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

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            result = view(request, self.list.id)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], self.list.remote_id)

        self.assertEqual(result.status_code, 302)

        self.list.refresh_from_db()
        self.assertEqual(self.list.name, "New Name")
        self.assertEqual(self.list.description, "wow")
        self.assertEqual(self.list.privacy, "direct")
        self.assertEqual(self.list.curation, "curated")

    def test_curate_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)

    def test_user_lists_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserLists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_user_lists_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserLists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, self.local_user.username)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
