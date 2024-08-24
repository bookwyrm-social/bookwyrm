""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


class Relationship(TestCase):
    """following, blocking, stuff like that"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need some users for this"""
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
            )
            self.another_local_user = models.User.objects.create_user(
                "bird", "bird@bird.com", "birdword", local=True, localname="bird"
            )
        self.local_user.remote_id = "http://local.com/user/mouse"
        self.local_user.save(broadcast=False, update_fields=["remote_id"])

    def test_report_local_user(self):
        """a report/flag within an instance"""
        report = models.Report.objects.create(
            user=self.local_user,
            note="oh no bad",
            reported_user=self.another_local_user,
        )

        activity = report.to_activity()
        self.assertEqual(activity["type"], "Flag")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["to"], self.another_local_user.remote_id)
        self.assertEqual(activity["object"], [self.another_local_user.remote_id])
        self.assertEqual(report.get_recipients(), [])

    def test_report_remote_user_with_broadcast(self):
        """a report to the outside needs to broadcast"""
        with patch("bookwyrm.models.report.Report.broadcast") as broadcast_mock:
            report = models.Report.objects.create(
                user=self.local_user,
                note="oh no bad",
                reported_user=self.remote_user,
                allow_broadcast=True,
            )
        self.assertEqual(broadcast_mock.call_count, 1)
        self.assertEqual(report.get_recipients(), [self.remote_user.inbox])
