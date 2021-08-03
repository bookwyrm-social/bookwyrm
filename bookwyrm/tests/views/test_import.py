""" test for app action functionality """
from unittest.mock import patch
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class ImportViews(TestCase):
    """goodreads import views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_import_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Import.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_import_status(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ImportStatus.as_view()
        import_job = models.ImportJob.objects.create(user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.tasks.app.AsyncResult") as async_result:
            async_result.return_value = []
            result = view(request, import_job.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_retry_import(self):
        """retry failed items"""
        view = views.ImportStatus.as_view()
        import_job = models.ImportJob.objects.create(
            user=self.local_user, privacy="unlisted"
        )
        request = self.factory.post("")
        request.user = self.local_user

        with patch("bookwyrm.importers.Importer.start_import"):
            view(request, import_job.id)

        self.assertEqual(models.ImportJob.objects.count(), 2)
        retry_job = models.ImportJob.objects.last()

        self.assertTrue(retry_job.retry)
        self.assertEqual(retry_job.user, self.local_user)
        self.assertEqual(retry_job.privacy, "unlisted")
