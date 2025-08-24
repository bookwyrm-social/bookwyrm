""" test for files maintenance page functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms, models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class FilesMaintenanceViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        cls.local_user.groups.set([group])
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_files_maintenance_get(self):
        """there are so many views, this just makes sure it LOADS"""

        view = views.FilesMaintenance.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_files_maintenance_get_with_schedule(self):
        """there are so many views, this just makes sure it LOADS"""

        schedule = IntervalSchedule.objects.create(every=1, period="days")
        PeriodicTask.objects.create(
            interval=schedule,
            name="delete-exports-task",
            task="bookwyrm.models.housekeeping.start_export_deletions",
        )

        view = views.FilesMaintenance.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_schedule_delete_export_file(self):
        """Schedule the task"""
        self.assertFalse(IntervalSchedule.objects.exists())

        form = forms.IntervalScheduleForm()
        form.data["every"] = 1
        form.data["period"] = "days"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        response = views.schedule_export_delete_task(request)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(IntervalSchedule.objects.exists())

    def test_export_files_set_expiry(self):
        """does setting the expiry time change the setting?"""

        form = forms.ExportFileExpiryForm()
        form.data["hours"] = "48"
        view = views.set_export_expiry_age
        request = self.factory.post("", form.data)
        request.user = self.local_user
        site = models.SiteSettings.objects.get()

        self.assertEqual(site.export_files_lifetime_hours, 72)

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        site.refresh_from_db()

        self.assertEqual(site.export_files_lifetime_hours, 48)
