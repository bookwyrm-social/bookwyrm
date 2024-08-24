""" testing models """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.models.job import ChildJob, ParentJob


class TestParentJob(TestCase):
    """job manager"""

    @classmethod
    def setUpTestData(cls):
        """we're trying to transport user data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
            )

    def test_complete_job(self):
        """mark a job as complete"""
        job = ParentJob.objects.create(user=self.local_user)
        self.assertFalse(job.complete)
        self.assertEqual(job.status, "pending")

        job.complete_job()

        job.refresh_from_db()
        self.assertTrue(job.complete)
        self.assertEqual(job.status, "complete")

    def test_complete_job_with_children(self):
        """mark a job with children as complete"""
        job = ParentJob.objects.create(user=self.local_user)
        child = ChildJob.objects.create(parent_job=job)
        self.assertFalse(child.complete)
        self.assertEqual(child.status, "pending")

        job.complete_job()

        child.refresh_from_db()
        self.assertEqual(child.status, "stopped")

    def test_pending_child_jobs(self):
        """queryset of child jobs for a parent"""
        job = ParentJob.objects.create(user=self.local_user)
        child = ChildJob.objects.create(parent_job=job)
        ChildJob.objects.create(parent_job=job, complete=True)

        self.assertEqual(job.pending_child_jobs.count(), 1)
        self.assertEqual(job.pending_child_jobs.first(), child)


class TestChildJob(TestCase):
    """job manager"""

    @classmethod
    def setUpTestData(cls):
        """we're trying to transport user data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
            )

    def test_complete_job(self):
        """a child job completed, so its parent is complete"""
        job = ParentJob.objects.create(user=self.local_user)
        child = ChildJob.objects.create(parent_job=job)
        self.assertFalse(job.complete)

        child.complete_job()

        job.refresh_from_db()
        self.assertTrue(job.complete)
        self.assertEqual(job.status, "complete")

    def test_complete_job_with_siblings(self):
        """a child job completed, but its parent is not complete"""
        job = ParentJob.objects.create(user=self.local_user)
        child = ChildJob.objects.create(parent_job=job)
        ChildJob.objects.create(parent_job=job)
        self.assertFalse(job.complete)

        child.complete_job()

        job.refresh_from_db()
        self.assertFalse(job.complete)

    def test_set_status(self):
        """a parent job is activated when a child task is activated"""
        job = ParentJob.objects.create(user=self.local_user)
        child = ChildJob.objects.create(parent_job=job)
        self.assertEqual(job.status, "pending")

        child.set_status("active")
        job.refresh_from_db()

        self.assertEqual(job.status, "active")
