""" test for app action functionality """
from unittest.mock import patch

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse


class BookViews(TestCase):
    """books books books"""

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
            physical_format="paperback",
        )

        models.SiteSettings.objects.create()

    def test_editions_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Editions.as_view()
        request = self.factory.get("")
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertTrue("paperback" in result.context_data["formats"])

    def test_editions_page_filtered(self):
        """editions view with filters"""
        models.Edition.objects.create(
            title="Fish",
            physical_format="okay",
            parent_work=self.work,
        )
        view = views.Editions.as_view()
        request = self.factory.get("")
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["editions"].object_list), 2)
        self.assertEqual(len(result.context_data["formats"]), 2)
        self.assertTrue("paperback" in result.context_data["formats"])
        self.assertTrue("okay" in result.context_data["formats"])

        request = self.factory.get("", {"q": "fish"})
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["editions"].object_list), 1)

        request = self.factory.get("", {"q": "okay"})
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["editions"].object_list), 1)

        request = self.factory.get("", {"format": "okay"})
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["editions"].object_list), 1)

    def test_editions_page_api(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Editions.as_view()
        request = self.factory.get("")
        with patch("bookwyrm.views.editions.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.work.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
    def test_switch_edition(self, *_):
        """updates user's relationships to a book"""
        work = models.Work.objects.create(title="test work")
        edition1 = models.Edition.objects.create(title="first ed", parent_work=work)
        edition2 = models.Edition.objects.create(title="second ed", parent_work=work)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = models.Shelf.objects.create(name="Test Shelf", user=self.local_user)
            models.ShelfBook.objects.create(
                book=edition1,
                user=self.local_user,
                shelf=shelf,
            )
        models.ReadThrough.objects.create(user=self.local_user, book=edition1)

        self.assertEqual(models.ShelfBook.objects.get().book, edition1)
        self.assertEqual(models.ReadThrough.objects.get().book, edition1)
        request = self.factory.post("", {"edition": edition2.id})
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.switch_edition(request)

        self.assertEqual(models.ShelfBook.objects.get().book, edition2)
        self.assertEqual(models.ReadThrough.objects.get().book, edition2)
