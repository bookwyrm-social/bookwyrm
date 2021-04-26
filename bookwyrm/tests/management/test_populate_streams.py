""" test populating user streams """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models
from bookwyrm.management.commands.populate_streams import populate_streams


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class Activitystreams(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """we need some stuff"""
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        self.another_user = models.User.objects.create_user(
            "nutria", "nutria@nutria.nutria", "password", local=True, localname="nutria"
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
        self.book = models.Edition.objects.create(title="test book")

    def test_populate_streams(self, _):
        """make sure the function on the redis manager gets called"""
        with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
            models.Comment.objects.create(
                user=self.local_user, content="hi", book=self.book
            )

        with patch(
            "bookwyrm.activitystreams.ActivityStream.populate_store"
        ) as redis_mock:
            populate_streams()
        self.assertEqual(redis_mock.call_count, 6)  # 2 users x 3 streams
