""" test populating user streams """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models
from bookwyrm.management.commands.populate_lists_streams import populate_lists_streams


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need some stuff"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
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
            models.User.objects.create_user(
                "gerbil",
                "gerbil@nutria.nutria",
                "password",
                local=True,
                localname="gerbil",
                is_active=False,
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

    def test_populate_streams(self, *_):
        """make sure the function on the redis manager gets called"""
        with patch("bookwyrm.lists_stream.populate_lists_task.delay") as list_mock:
            populate_lists_streams()
        self.assertEqual(list_mock.call_count, 2)  # 2 users
