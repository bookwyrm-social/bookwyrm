""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class ReportViews(TestCase):
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
            self.rat = models.User.objects.create_user(
                "rat@local.com",
                "rat@mouse.mouse",
                "password",
                local=True,
                localname="rat",
            )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="moderator")
        self.local_user.groups.set([group])
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_reports_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ReportsAdmin.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_reports_page_with_data(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ReportsAdmin.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        models.Report.objects.create(reporter=self.local_user, user=self.rat)

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_report_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ReportAdmin.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        report = models.Report.objects.create(reporter=self.local_user, user=self.rat)

        result = view(request, report.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_report_action(self):
        """action on a report"""
        view = views.ReportAdmin.as_view()
        request = self.factory.post("", {"note": "hi"})
        request.user = self.local_user
        report = models.Report.objects.create(reporter=self.local_user, user=self.rat)

        view(request, report.id)

        action = models.ReportAction.objects.get()
        self.assertEqual(action.user, self.local_user)
        self.assertEqual(action.note, "hi")
        self.assertEqual(action.report, report)
        self.assertEqual(action.action_type, "comment")

    def test_resolve_report(self):
        """toggle report resolution status"""
        report = models.Report.objects.create(reporter=self.local_user, user=self.rat)
        self.assertFalse(report.resolved)
        self.assertFalse(models.ReportAction.objects.exists())
        request = self.factory.post("")
        request.user = self.local_user

        # resolve
        views.resolve_report(request, report.id)
        report.refresh_from_db()
        self.assertTrue(report.resolved)

        # check that the action was noted
        self.assertTrue(
            models.ReportAction.objects.filter(
                report=report, action_type="resolve", user=self.local_user
            ).exists()
        )

        # un-resolve
        views.resolve_report(request, report.id)
        report.refresh_from_db()
        self.assertFalse(report.resolved)

        # check that the action was noted
        self.assertTrue(
            models.ReportAction.objects.filter(
                report=report, action_type="reopen", user=self.local_user
            ).exists()
        )

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_suspend_user(self, *_):
        """toggle whether a user is able to log in"""
        self.assertTrue(self.rat.is_active)
        request = self.factory.post("")
        request.user = self.local_user

        # de-activate
        views.suspend_user(request, self.rat.id)
        self.rat.refresh_from_db()
        self.assertFalse(self.rat.is_active)

        # re-activate
        views.unsuspend_user(request, self.rat.id)
        self.rat.refresh_from_db()
        self.assertTrue(self.rat.is_active)

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_delete_user(self, *_):
        """toggle whether a user is able to log in"""
        self.assertTrue(self.rat.is_active)
        request = self.factory.post("", {"password": "password"})
        request.user = self.local_user

        # de-activate
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            views.moderator_delete_user(request, self.rat.id)
        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Delete")

        self.rat.refresh_from_db()
        self.assertFalse(self.rat.is_active)
        self.assertEqual(self.rat.deactivation_reason, "moderator_deletion")

    def test_delete_user_error(self, *_):
        """toggle whether a user is able to log in"""
        self.assertTrue(self.rat.is_active)
        request = self.factory.post("", {"password": "wrong password"})
        request.user = self.local_user

        result = views.moderator_delete_user(request, self.rat.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.rat.refresh_from_db()
        self.assertTrue(self.rat.is_active)
