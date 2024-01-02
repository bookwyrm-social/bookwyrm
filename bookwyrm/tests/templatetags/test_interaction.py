""" style fixes and lookups for templates """
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import interaction


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class InteractionTags(TestCase):
    """lotta different things here"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
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
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                remote_id="http://example.com/rat",
                local=False,
            )
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_user_liked(self, *_):
        """did a user like a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_liked(self.user, status))
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.Favorite.objects.create(user=self.user, status=status)
        self.assertTrue(interaction.get_user_liked(self.user, status))

    def test_get_user_boosted(self, *_):
        """did a user boost a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_boosted(self.user, status))
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.Boost.objects.create(user=self.user, boosted_status=status)
        self.assertTrue(interaction.get_user_boosted(self.user, status))
