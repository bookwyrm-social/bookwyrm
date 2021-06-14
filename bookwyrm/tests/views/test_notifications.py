""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class NotificationViews(TestCase):
    """notifications"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_notifications_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
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
