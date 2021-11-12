""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.remove_book_statuses_task.delay")
class ShelfViews(TestCase):
    """tag views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
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
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        models.SiteSettings.objects.create()

        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_shelf_page_all_books(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Shelf.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.local_user.username)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_shelf_page_all_books_anonymous(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Shelf.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.local_user.username)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_shelf_page_sorted(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Shelf.as_view()
        shelf = self.local_user.shelf_set.first()
        request = self.factory.get("", {"sort": "author"})
        request.user = self.local_user
        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.local_user.username, shelf.identifier)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_shelf_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Shelf.as_view()
        shelf = self.local_user.shelf_set.first()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.local_user.username, shelf.identifier)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.local_user.username, shelf.identifier)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?page=1")
        request.user = self.local_user
        with patch("bookwyrm.views.shelf.shelf.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.local_user.username, shelf.identifier)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_edit_shelf_privacy(self, *_):
        """set name or privacy on shelf"""
        view = views.Shelf.as_view()
        shelf = self.local_user.shelf_set.get(identifier="to-read")
        self.assertEqual(shelf.privacy, "public")

        request = self.factory.post(
            "",
            {
                "privacy": "unlisted",
                "user": self.local_user.id,
                "name": "To Read",
            },
        )
        request.user = self.local_user
        view(request, self.local_user.username, shelf.identifier)
        shelf.refresh_from_db()

        self.assertEqual(shelf.privacy, "unlisted")

    def test_edit_shelf_name(self, *_):
        """change the name of an editable shelf"""
        view = views.Shelf.as_view()
        shelf = models.Shelf.objects.create(name="Test Shelf", user=self.local_user)
        self.assertEqual(shelf.privacy, "public")

        request = self.factory.post(
            "", {"privacy": "public", "user": self.local_user.id, "name": "cool name"}
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, request.user.username, shelf.identifier)
        shelf.refresh_from_db()

        self.assertEqual(shelf.name, "cool name")
        self.assertEqual(shelf.identifier, f"testshelf-{shelf.id}")

    def test_edit_shelf_name_not_editable(self, *_):
        """can't change the name of an non-editable shelf"""
        view = views.Shelf.as_view()
        shelf = self.local_user.shelf_set.get(identifier="to-read")
        self.assertEqual(shelf.privacy, "public")

        request = self.factory.post(
            "", {"privacy": "public", "user": self.local_user.id, "name": "cool name"}
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, request.user.username, shelf.identifier)

        self.assertEqual(shelf.name, "To Read")
