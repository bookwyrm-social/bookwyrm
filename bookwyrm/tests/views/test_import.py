""" test for app action functionality """
import pathlib
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


class ImportViews(TestCase):
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

    def test_start_import(self):
        """retry failed items"""
        view = views.Import.as_view()
        form = forms.ImportForm()
        form.data["source"] = "LibraryThing"
        form.data["privacy"] = "public"
        form.data["include_reviews"] = False
        csv_file = pathlib.Path(__file__).parent.joinpath("../data/goodreads.csv")
        form.data["csv_file"] = SimpleUploadedFile(
            csv_file, open(csv_file, "rb").read(), content_type="text/csv"
        )

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.importers.Importer.start_import"):
            view(request)
        job = models.ImportJob.objects.get()
        self.assertFalse(job.include_reviews)
        self.assertEqual(job.privacy, "public")

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
