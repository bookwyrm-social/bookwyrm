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
            self.another_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            self.status = models.Status.objects.create(
                content="hi", user=self.local_user
            )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_notifications_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_status_notifications(self):
        """there are so many views, this just makes sure it LOADS"""
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="FAVORITE",
            related_status=self.status,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="BOOST",
            related_status=self.status,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="MENTION",
            related_status=self.status,
        )
        self.status.reply_parent = self.status
        self.status.save(broadcast=False)
        models.Notification.notify(
            self.local_user,
            self.another_user,
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

    def test_notifications_page_follow_request(self):
        """import completed notification"""
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="FOLLOW_REQUEST",
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

    def test_notifications_page_follows(self):
        """import completed notification"""
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="FOLLOW",
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

    def test_notifications_page_report(self):
        """import completed notification"""
        report = models.Report.objects.create(
            user=self.another_user,
            reporter=self.local_user,
        )
        notification = models.Notification.objects.create(
            user=self.local_user,
            notification_type="REPORT",
        )
        notification.related_reports.add(report)

        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

    def test_notifications_page_import(self):
        """import completed notification"""
        import_job = models.ImportJob.objects.create(user=self.local_user, mappings={})
        models.Notification.objects.create(
            user=self.local_user, notification_type="IMPORT", related_import=import_job
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_list(self):
        """Adding books to lists"""
        book = models.Edition.objects.create(title="shape")
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.lists_stream.remove_list_task.delay"):
            book_list = models.List.objects.create(user=self.local_user, name="hi")
            item = models.ListItem.objects.create(
                book=book, user=self.another_user, book_list=book_list, order=1
            )
        models.Notification.notify_list_item(self.local_user, item)
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_invite(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="INVITE",
            related_group=group,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_accept(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="ACCEPT",
            related_group=group,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_join(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="JOIN",
            related_group=group,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_leave(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="LEAVE",
            related_group=group,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_remove(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="REMOVE",
            related_group=group,
        )
        view = views.Notifications.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_notifications_page_group_changes(self):
        """group related notifications"""
        group = models.Group.objects.create(user=self.another_user, name="group")
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="GROUP_PRIVACY",
            related_group=group,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="GROUP_NAME",
            related_group=group,
        )
        models.Notification.notify(
            self.local_user,
            self.another_user,
            notification_type="GROUP_DESCRIPTION",
            related_group=group,
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
