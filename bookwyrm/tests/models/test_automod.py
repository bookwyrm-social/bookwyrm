"""test for app action functionality"""
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm.models.antispam import automod_task


class AutomodModel(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
            is_superuser=True,
        )
        cls.another_user = models.User.objects.create_user(
            "rat@local.com",
            "rat@mouse.mouse",
            "password",
            local=True,
            localname="rat",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def test_automod_task_no_rules(self):
        """nothing to see here"""
        self.assertFalse(models.Report.objects.exists())
        automod_task()
        self.assertFalse(models.Report.objects.exists())
        self.assertFalse(models.Notification.objects.exists())

    def test_automod_task_user(self):
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
        self.assertEqual(models.Notification.objects.count(), 1)

    def test_automod_task_user_existing_reports(self):
        """scan activity"""
        self.assertFalse(models.Report.objects.exists())
        models.AutoMod.objects.create(
            string_match="hi",
            flag_users=True,
            flag_statuses=True,
            created_by=self.local_user,
        )
        models.Report.objects.create(
            user=self.local_user,
            reported_user=self.another_user,
            allow_broadcast=False,
        )

        self.another_user.name = "okay hi"
        self.another_user.save(broadcast=False, update_fields=["name"])

        automod_task()

        reports = models.Report.objects.all()
        self.assertEqual(reports.count(), 1)

    def test_automod_status(self):
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
        self.assertEqual(reports.first().statuses.first(), status)
        self.assertEqual(reports.first().user, self.local_user)
        self.assertEqual(models.Notification.objects.count(), 1)
