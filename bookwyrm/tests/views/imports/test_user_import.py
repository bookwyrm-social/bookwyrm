""" test for app action functionality """
import pathlib
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


class ImportUserViews(TestCase):
    """user import views"""

    # pylint: disable=invalid-name
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

    def test_get_user_import_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserImport.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_user_import_post(self):
        """does the import job start?"""

        view = views.UserImport.as_view()
        form = forms.ImportUserForm()
        archive_file = pathlib.Path(__file__).parent.joinpath(
            "../../data/bookwyrm_account_export.tar.gz"
        )

        form.data["archive_file"] = SimpleUploadedFile(
            # pylint: disable=consider-using-with
            archive_file,
            open(archive_file, "rb").read(),
            content_type="application/gzip",
        )

        form.data["include_user_settings"] = ""
        form.data["include_goals"] = "on"

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.bookwyrm_import_job.BookwyrmImportJob.start_job"):
            view(request)
        job = models.BookwyrmImportJob.objects.get()
        self.assertEqual(job.required, ["include_goals"])
