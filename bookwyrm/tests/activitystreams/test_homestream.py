""" testing activitystreams """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import activitystreams, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class Activitystreams(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )
            self.another_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.nutria",
                "password",
                local=True,
                localname="nutria",
            )
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

    def test_homestream_get_audience(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.HomeStream().get_audience(status)
        self.assertFalse(users.exists())

    def test_homestream_get_audience_with_mentions(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        status.mention_users.add(self.local_user)
        users = activitystreams.HomeStream().get_audience(status)
        self.assertFalse(self.local_user in users)
        self.assertFalse(self.another_user in users)

    def test_homestream_get_audience_with_relationship(self, *_):
        """get a list of users that should see a status"""
        self.remote_user.followers.add(self.local_user)
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.HomeStream().get_audience(status)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
