""" test for app action functionality """
from unittest.mock import patch
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views
from bookwyrm.tests.validate_html import validate_html


class NotificationViews(TestCase):
    """notifications"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.status = models.Status.objects.create(
                content="hi",
                user=self.local_user,
            )
        models.SiteSettings.objects.create()

    def test_notifications_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_notifications(self):
        """there are so many views, this just makes sure it LOADS"""
        models.Notification.objects.create(
            user=self.local_user,
            notification_type="FAVORITE",
            related_status=self.status,
        )
        models.Notification.objects.create(
            user=self.local_user,
            notification_type="BOOST",
            related_status=self.status,
        )
        models.Notification.objects.create(
            user=self.local_user,
            notification_type="MENTION",
            related_status=self.status,
        )
        self.status.reply_parent = self.status
        self.status.save(broadcast=False)
        models.Notification.objects.create(
            user=self.local_user,
            notification_type="REPLY",
            related_status=self.status,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_clear_notifications(self):
        """erase notifications"""
        models.Notification.objects.create(
            user=self.local_user, notification_type="FAVORITE"
        )
        models.Notification.objects.create(
            user=self.local_user, notification_type="MENTION", read=True
        )
        self.assertEqual(models.Notification.objects.count(), 2)
        view = views.Notifications.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        result = view(request)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(models.Notification.objects.count(), 1)
