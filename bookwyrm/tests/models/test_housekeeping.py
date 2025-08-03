""" test file management """
from datetime import datetime, timedelta, timezone
from os import listdir
import pathlib
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase

from bookwyrm import models
from bookwyrm.settings import DOMAIN
from bookwyrm.models.housekeeping import (
    CleanUpUserExportFilesJob,
    delete_user_export_file_task,
    start_export_deletions,
)


class TestCleanUpExportFiles(TestCase):
    """export and import files should be deleted periodically"""

    def setUp(self):
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            self.user = models.User.objects.create_user(
                f"mouse@{DOMAIN}",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
                name="hi",
                summary="a summary",
                bookwyrm_user=False,
            )

            expiry_date = datetime.now(timezone.utc) - timedelta(hours=2)
            self.job = CleanUpUserExportFilesJob.objects.create(
                user=self.user, expiry_date=expiry_date
            )

            models.SiteSettings.objects.create()

    def test_export_file_deleted(self, *_):
        """did the file actually get deleted?"""

        export_updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        export = models.BookwyrmExportJob.objects.create(
            user=self.user,
            export_data=ContentFile(b"..", name="zzz_testfile.tar.gz"),
            updated_date=export_updated_date,
            complete=True,
        )

        self.assertTrue(export.export_data.name)
        delete_user_export_file_task(job_id=self.job.id, export_id=export.id)
        export.refresh_from_db()
        self.assertFalse(export.export_data.name)

    def test_import_file_deleted(self, *_):
        """did the file actually get deleted?"""

        updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        import_job = models.BookwyrmImportJob.objects.create(
            user=self.user,
            archive_file=ContentFile(b"xx", name="zzz_testfile.tar.gz"),
            updated_date=updated_date,
            complete=True,
            required=[],
        )

        self.assertTrue(import_job.archive_file.name)
        delete_user_export_file_task(job_id=self.job.id, import_id=import_job.id)
        import_job.refresh_from_db()
        self.assertFalse(import_job.archive_file.name)

    def test_renamed_file_deleted(self, *_):
        """files with duplicate names get renamed like filename.tar7x9e.gz"""

        export_updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        export = models.BookwyrmExportJob.objects.create(
            user=self.user,
            export_data=ContentFile(b"...", name="zzz_testfile.tar.gz"),
            updated_date=export_updated_date,
            complete=True,
        )

        self.assertTrue(export.export_data)
        export.refresh_from_db()
        delete_user_export_file_task(job_id=self.job.id, export_id=export.id)
        export.refresh_from_db()
        self.assertFalse(export.export_data.name)

    def test_start_export_deletions(self, *_):
        """does start_export_deletions actually start a job?"""

        self.assertEqual(models.CleanUpUserExportFilesJob.objects.count(), 1)

        start_export_deletions(user=self.user.id)

        self.assertEqual(models.CleanUpUserExportFilesJob.objects.count(), 2)
        self.assertNotEqual(
            models.CleanUpUserExportFilesJob.objects.last().status, "pending"
        )

    def tearDown(self):
        """clean up any files"""

        for filename in listdir("exports"):

            if "zzz_testfile.tar" in filename:
                pathlib.Path.unlink(f"exports/{filename}")
