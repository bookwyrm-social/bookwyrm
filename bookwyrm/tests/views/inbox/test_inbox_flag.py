""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxFlag(TestCase):
    """inbox tests"""

    @classmethod
    def setUpTestData(cls):  # pylint: disable=invalid-name
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
        cls.local_user.remote_id = "https://example.com/user/mouse"
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

        models.SiteSettings.objects.create()

    @responses.activate
    def test_flag_local_user(self):
        """Serialize a report from a remote server"""
        # TODO: is this actually what a Flag object from mastodon looks like?
        activity = {
            "id": "https://example.com/shelfbook/6189#add",
            "type": "Flag",
            "actor": self.remote_user.remote_id,
            "object": {},
            "to": self.local_user.remote_id,
            "cc": ["https://example.com/user/mouse/followers"],
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        # a report should now exist
        self.assertTrue(
            models.Report.objects.filter(
                user=self.remote_user, reported_user=self.local_user
            ).exists()
        )
