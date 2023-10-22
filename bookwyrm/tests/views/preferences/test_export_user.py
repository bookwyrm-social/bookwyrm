""" test for user export app functionality """
from unittest.mock import patch

from django.http import HttpResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class ExportUserViews(TestCase):
    """exporting user data"""

    def setUp(self):
        self.factory = RequestFactory()
        models.SiteSettings.objects.create()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "hugh@example.com",
                "hugh@example.com",
                "password",
                local=True,
                localname="Hugh",
                summary="just a test account",
                remote_id="https://example.com/users/hugh",
                preferred_timezone="Australia/Broken_Hill",
            )

    def test_export_user_get(self, *_):
        """request export"""
        request = self.factory.get("")
        request.user = self.local_user
        result = views.ExportUser.as_view()(request)
        validate_html(result.render())

    def test_trigger_export_user_file(self, *_):
        """simple user export"""

        request = self.factory.post("")
        request.user = self.local_user
        with patch("bookwyrm.models.bookwyrm_export_job.start_export_task.delay"):
            export = views.ExportUser.as_view()(request)
        self.assertIsInstance(export, HttpResponse)
        self.assertEqual(export.status_code, 302)

        jobs = models.bookwyrm_export_job.BookwyrmExportJob.objects.count()
        self.assertEqual(jobs, 1)
