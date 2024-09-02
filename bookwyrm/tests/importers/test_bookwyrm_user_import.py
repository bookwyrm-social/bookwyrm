""" testing bookwyrm user import """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import models
from bookwyrm.importers import BookwyrmImporter


class BookwyrmUserImport(TestCase):
    """importing from BookWyrm user import"""

    def setUp(self):
        """setting stuff up"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            self.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )

    def test_create_retry_job(self):
        """test retrying a user import"""

        job = models.bookwyrm_import_job.BookwyrmImportJob.objects.create(
            user=self.user, required=[]
        )

        job.complete_job()
        self.assertEqual(job.retry, False)
        self.assertEqual(
            models.bookwyrm_import_job.BookwyrmImportJob.objects.count(), 1
        )

        # retry the job
        importer = BookwyrmImporter()
        importer.create_retry_job(user=self.user, original_job=job)

        retry_job = models.bookwyrm_import_job.BookwyrmImportJob.objects.last()

        self.assertEqual(
            models.bookwyrm_import_job.BookwyrmImportJob.objects.count(), 2
        )
        self.assertEqual(retry_job.retry, True)
        self.assertNotEqual(job.id, retry_job.id)
