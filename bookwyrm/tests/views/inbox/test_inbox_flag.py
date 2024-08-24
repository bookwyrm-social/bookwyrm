""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


class InboxFlag(TestCase):
    """inbox tests"""

    @classmethod
    def setUpTestData(cls):
        """basic user and book data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
            )
        cls.local_user.save(broadcast=False, update_fields=["remote_id"])
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        cls.status = models.Status.objects.create(
            user=cls.local_user, content="bad things"
        )

        models.SiteSettings.objects.create()

    def test_flag_local_user(self):
        """Serialize a report from a remote server"""
        activity = {
            "id": "https://example.com/settings/reports/6189",
            "type": "Flag",
            "actor": self.remote_user.remote_id,
            "object": [self.local_user.remote_id],
            "to": self.local_user.remote_id,
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "content": "hello hello",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        # a report should now exist
        report = models.Report.objects.get(
            user=self.remote_user, reported_user=self.local_user
        )
        self.assertEqual(report.note, "hello hello")

    def test_flag_local_user_with_statuses(self):
        """A report that includes a user and a status"""
        activity = {
            "id": "https://example.com/settings/reports/6189",
            "type": "Flag",
            "actor": self.remote_user.remote_id,
            "object": [self.local_user.remote_id, self.status.remote_id],
            "to": self.local_user.remote_id,
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "content": "hello hello",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        # a report should now exist
        report = models.Report.objects.get(
            user=self.remote_user, reported_user=self.local_user
        )
        self.assertEqual(report.note, "hello hello")
        self.assertEqual(report.statuses.first(), self.status)
