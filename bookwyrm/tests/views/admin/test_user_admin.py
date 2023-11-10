""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.models.report import USER_PERMS
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class UserAdminViews(TestCase):
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
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="moderator")
        self.local_user.groups.set([group])
        models.SiteSettings.objects.create()

    def test_user_admin_list_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserAdminList.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_user_admin_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserAdmin.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_user_admin_page_post(self, *_):
        """set the user's group"""
        group = Group.objects.get(name="editor")
        self.assertEqual(
            list(self.local_user.groups.values_list("name", flat=True)), ["moderator"]
        )

        view = views.UserAdmin.as_view()
        request = self.factory.post("", {"groups": [group.id]})
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            result = view(request, self.local_user.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(
            list(self.local_user.groups.values_list("name", flat=True)), ["editor"]
        )

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    def test_user_admin_page_post_with_report(self, *_):
        """set the user's group"""
        group = Group.objects.get(name="editor")
        self.assertEqual(
            list(self.local_user.groups.values_list("name", flat=True)), ["moderator"]
        )

        report = models.Report.objects.create(
            user=self.local_user, reporter=self.local_user
        )

        view = views.UserAdmin.as_view()
        request = self.factory.post("", {"groups": [group.id]})
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            result = view(request, self.local_user.id, report.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(
            list(self.local_user.groups.values_list("name", flat=True)), ["editor"]
        )
        # make sure a report action was created
        self.assertTrue(
            models.ReportAction.objects.filter(
                report=report, action_type=USER_PERMS
            ).exists()
        )
