"""test for app action functionality"""

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class AutomodViews(TestCase):
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
        view = views.DataQuality.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_data_quality_get_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DataQuality.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
