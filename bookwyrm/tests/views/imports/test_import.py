""" test for app action functionality """
import pathlib
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


class ImportViews(TestCase):
    """goodreads import views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
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
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_import_status(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ImportStatus.as_view()
        import_job = models.ImportJob.objects.create(user=self.local_user, mappings={})
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, import_job.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_import_status_reformat(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ImportStatus.as_view()
        import_job = models.ImportJob.objects.create(user=self.local_user, mappings={})
        request = self.factory.post("")
        request.user = self.local_user
        with patch(
            "bookwyrm.importers.goodreads_import.GoodreadsImporter.update_legacy_job"
        ) as mock:
            result = view(request, import_job.id)
        self.assertEqual(mock.call_args[0][0], import_job)

        self.assertEqual(result.status_code, 302)

    def test_start_import(self):
        """start a job"""
        view = views.Import.as_view()
        form = forms.ImportForm()
        form.data["source"] = "Goodreads"
        form.data["privacy"] = "public"
        form.data["include_reviews"] = False
        csv_file = pathlib.Path(__file__).parent.joinpath("../../data/goodreads.csv")
        form.data["csv_file"] = SimpleUploadedFile(
            # pylint: disable=consider-using-with
            csv_file,
            open(csv_file, "rb").read(),
            content_type="text/csv",
        )

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.importers.Importer.start_import"):
            view(request)
        job = models.ImportJob.objects.get()
        self.assertFalse(job.include_reviews)
        self.assertEqual(job.privacy, "public")

    def test_retry_item(self):
        """try again on a single row"""
        job = models.ImportJob.objects.create(user=self.local_user, mappings={})
        item = models.ImportItem.objects.create(
            index=0,
            job=job,
            fail_reason="no match",
            data={},
            normalized_data={},
        )
        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.importers.importer.import_item_task.delay") as mock:
            views.retry_item(request, job.id, item.id)
        self.assertEqual(mock.call_count, 1)
