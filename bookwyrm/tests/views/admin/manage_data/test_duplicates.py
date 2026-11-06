"""test for app action functionality"""

from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms, models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class DuplicatesViews(TestCase):
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
        )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        cls.local_user.groups.set([group])

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_data_quality_get(self):
        """there are so many views, this just makes sure it LOADS"""
        schedule = IntervalSchedule.objects.create(every=1, period="days")
        PeriodicTask.objects.create(
            interval=schedule,
            name="dedupe-task",
            task="bookwyrm.models.housekeeping.mark_duplicate_data_task",
        )
        view = views.Duplicates.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_data_quality_get_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Duplicates.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_run_deduplication_scan_task(self):
        """start a task"""
        request = self.factory.post("")
        request.user = self.local_user

        with patch(
            "bookwyrm.models.housekeeping.mark_duplicate_data_task.delay"
        ) as mock:
            result = views.run_deduplication_scan_task(request)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(result.status_code, 302)

    def test_schedule_deduplication_scan_task(self):
        """start a task"""
        form = forms.IntervalScheduleForm()
        form.data["scan-every"] = 1
        form.data["scan-period"] = "days"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = views.schedule_deduplication_scan_task(request)
        self.assertEqual(result.status_code, 302)
        interval = IntervalSchedule.objects.get()
        task = PeriodicTask.objects.get()
        self.assertEqual(interval.period, "days")
        self.assertEqual(interval.every, 1)
        self.assertEqual(task.name, "dedupe-scan-task")
        self.assertEqual(task.interval, interval)
        self.assertEqual(
            task.task, "bookwyrm.models.housekeeping.mark_duplicate_data_task"
        )

    def test_schedule_deduplication_scan_task_invalid(self):
        """start a task"""
        form = forms.IntervalScheduleForm()
        form.data["scan-every"] = 0
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = views.schedule_deduplication_scan_task(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(IntervalSchedule.objects.count(), 0)
        self.assertEqual(PeriodicTask.objects.count(), 0)

    def test_schedule_deduplication_task(self):
        """start a task"""
        form = forms.IntervalScheduleForm()
        form.data["merge-every"] = 1
        form.data["merge-period"] = "days"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = views.schedule_deduplication_task(request)
        self.assertEqual(result.status_code, 302)
        interval = IntervalSchedule.objects.get()
        task = PeriodicTask.objects.get()
        self.assertEqual(interval.period, "days")
        self.assertEqual(interval.every, 1)
        self.assertEqual(task.name, "dedupe-merge-task")
        self.assertEqual(task.interval, interval)
        self.assertEqual(
            task.task, "bookwyrm.models.housekeeping.merge_duplicate_data_task"
        )

    def test_schedule_deduplication_task_invalid(self):
        """start a task"""
        form = forms.IntervalScheduleForm()
        form.data["merge-every"] = 0
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = views.schedule_deduplication_task(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(IntervalSchedule.objects.count(), 0)
        self.assertEqual(PeriodicTask.objects.count(), 0)

    def test_unschedule_deduplication_task(self):
        """start a task"""
        form = forms.IntervalScheduleForm()
        form.data["merge-every"] = 1
        form.data["merge-period"] = "days"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        views.schedule_deduplication_task(request)
        task = PeriodicTask.objects.get()

        request = self.factory.post("")
        request.user = self.local_user
        result = views.unschedule_deduplication_scan_task(request, task.id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(PeriodicTask.objects.count(), 0)
