""" test for app action functionality """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


class ReportViews(TestCase):
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
            self.rat = models.User.objects.create_user(
                "rat@local.com",
                "rat@mouse.mouse",
                "password",
                local=True,
                localname="rat",
            )
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            self.status = models.Status.objects.create(
                user=self.local_user,
                content="Test status",
            )
        models.SiteSettings.objects.create()

    def test_report_modal_view(self):
        """a user reports another user"""
        request = self.factory.get("")
        request.user = self.local_user
        result = views.Report.as_view()(request, self.local_user.id)

        validate_html(result.render())

    def test_report_modal_view_with_status(self):
        """a user reports another user"""
        request = self.factory.get("")
        request.user = self.local_user
        result = views.Report.as_view()(
            request, user_id=self.local_user.id, status_id=self.status.id
        )

        validate_html(result.render())

    def test_report_modal_view_with_link_domain(self):
        """a user reports another user"""
        link = models.Link.objects.create(
            url="http://example.com/hi",
            added_by=self.local_user,
        )
        request = self.factory.get("")
        request.user = self.local_user
        result = views.Report.as_view()(request, link_id=link.id)

        validate_html(result.render())

    def test_make_report(self):
        """a user reports another user"""
        form = forms.ReportForm()
        form.data["reporter"] = self.local_user.id
        form.data["user"] = self.rat.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        views.Report.as_view()(request)

        report = models.Report.objects.get()
        self.assertEqual(report.reporter, self.local_user)
        self.assertEqual(report.user, self.rat)

    def test_report_link(self):
        """a user reports a link as spam"""
        book = models.Edition.objects.create(title="hi")
        link = models.FileLink.objects.create(
            book=book, added_by=self.local_user, url="https://skdjfs.sdf"
        )
        domain = link.domain
        domain.status = "approved"
        domain.save()

        form = forms.ReportForm()
        form.data["reporter"] = self.local_user.id
        form.data["user"] = self.rat.id
        form.data["links"] = link.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        views.Report.as_view()(request)

        report = models.Report.objects.get()
        domain.refresh_from_db()
        self.assertEqual(report.links.first().id, link.id)
        self.assertEqual(domain.status, "pending")
