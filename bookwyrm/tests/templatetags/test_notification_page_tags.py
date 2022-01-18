""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import notification_page_tags


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class NotificationPageTags(TestCase):
    """lotta different things here"""

    def setUp(self):
        """create some filler objects"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
            )

    def test_related_status(self, *_):
        """gets the subclass model for a notification status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            status = models.Status.objects.create(content="hi", user=self.user)
        notification = models.Notification.objects.create(
            user=self.user, notification_type="MENTION", related_status=status
        )

        result = notification_page_tags.related_status(notification)
        self.assertIsInstance(result, models.Status)
