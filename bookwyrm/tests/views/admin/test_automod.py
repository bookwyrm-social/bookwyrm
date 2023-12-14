""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms, models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class AutomodViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
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
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="moderator")
        self.local_user.groups.set([group])
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_automod_rules_get(self):
        """there are so many views, this just makes sure it LOADS"""
        schedule = IntervalSchedule.objects.create(every=1, period="days")
        PeriodicTask.objects.create(
            interval=schedule,
            name="automod-task",
            task="bookwyrm.models.antispam.automod_task",
        )
        models.AutoMod.objects.create(created_by=self.local_user, string_match="hello")
        view = views.AutoMod.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_automod_rules_get_empty_with_schedule(self):
        """there are so many views, this just makes sure it LOADS"""
        schedule = IntervalSchedule.objects.create(every=1, period="days")
        PeriodicTask.objects.create(
            interval=schedule,
            name="automod-task",
            task="bookwyrm.models.antispam.automod_task",
        )
        view = views.AutoMod.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_automod_rules_get_empty_without_schedule(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.AutoMod.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_automod_rules_post(self):
        """there are so many views, this just makes sure it LOADS"""
        form = forms.AutoModRuleForm()
        form.data["string_match"] = "hello"
        form.data["flag_users"] = True
        form.data["flag_statuses"] = False
        form.data["created_by"] = self.local_user.id

        view = views.AutoMod.as_view()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        rule = models.AutoMod.objects.get()
        self.assertTrue(rule.flag_users)
        self.assertFalse(rule.flag_statuses)

    def test_schedule_automod_task(self):
        """Schedule the task"""
        self.assertFalse(IntervalSchedule.objects.exists())

        form = forms.IntervalScheduleForm()
        form.data["every"] = 1
        form.data["period"] = "days"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        response = views.schedule_automod_task(request)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(IntervalSchedule.objects.exists())
