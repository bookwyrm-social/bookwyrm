""" test for app action functionality """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm.models.antispam import automod_task


@patch("bookwyrm.models.Status.broadcast")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class AutomodModel(TestCase):
    """every response to a get request, html or json"""

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

    def test_automod_task_no_rules(self, *_):
        """nothing to see here"""
        self.assertFalse(models.Report.objects.exists())
        automod_task()
        self.assertFalse(models.Report.objects.exists())

    def test_automod_task_user(self, *_):
        """scan activity"""
        self.assertFalse(models.Report.objects.exists())
        models.AutoMod.objects.create(
            string_match="hi",
            flag_users=True,
            flag_statuses=True,
            created_by=self.local_user,
        )

        self.local_user.name = "okay hi"
        self.local_user.save(broadcast=False, update_fields=["name"])

        automod_task()

        reports = models.Report.objects.all()
        self.assertEqual(reports.count(), 1)
        self.assertEqual(reports.first().user, self.local_user)

    def test_automod_status(self, *_):
        """scan activity"""
        self.assertFalse(models.Report.objects.exists())
        models.AutoMod.objects.create(
            string_match="hi",
            flag_users=True,
            flag_statuses=True,
            created_by=self.local_user,
        )

        status = models.Status.objects.create(
            user=self.local_user, content="hello", content_warning="hi"
        )

        automod_task()

        reports = models.Report.objects.all()
        self.assertEqual(reports.count(), 1)
        self.assertEqual(reports.first().status, status)
        self.assertEqual(reports.first().user, self.local_user)
