""" test for app action functionality """
from unittest.mock import patch
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from bookwyrm.tests.validate_html import validate_html

from bookwyrm import models, views


class ImportManualReviewViews(TestCase):
    """goodreads import views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        models.SiteSettings.objects.create()
        self.job = models.ImportJob.objects.create(user=self.local_user, mappings={})

        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_import_troubleshoot_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ImportManualReview.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.tasks.app.AsyncResult") as async_result:
            async_result.return_value = []
            result = view(request, self.job.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_approve_item(self):
        """a guess is correct"""
        import_item = models.ImportItem.objects.create(
            index=0,
            job=self.job,
            book_guess=self.book,
            fail_reason="no match",
            data={},
            normalized_data={},
        )
        request = self.factory.post("")
        request.user = self.local_user

        with patch("bookwyrm.importers.importer.import_item_task.delay") as mock:
            views.approve_import_item(request, self.job.id, import_item.id)
        self.assertEqual(mock.call_count, 1)
        import_item.refresh_from_db()
        self.assertIsNone(import_item.fail_reason)
        self.assertIsNone(import_item.book_guess)
        self.assertEqual(import_item.book.id, self.book.id)

    def test_delete_item(self):
        """a guess is correct"""
        import_item = models.ImportItem.objects.create(
            index=0,
            job=self.job,
            book_guess=self.book,
            fail_reason="no match",
            data={},
            normalized_data={},
        )
        request = self.factory.post("")
        request.user = self.local_user

        views.delete_import_item(request, self.job.id, import_item.id)
        import_item.refresh_from_db()
        self.assertEqual(import_item.fail_reason, "no match")
        self.assertIsNone(import_item.book_guess)
        self.assertIsNone(import_item.book)
