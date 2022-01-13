""" style fixes and lookups for templates """
import re
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import utilities


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class UtilitiesTags(TestCase):
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
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                remote_id="http://example.com/rat",
                local=False,
            )
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_user_identifer_local(self, *_):
        """fall back to the simplest uid available"""
        self.assertNotEqual(self.user.username, self.user.localname)
        self.assertEqual(utilities.get_user_identifier(self.user), "mouse")

    def test_get_user_identifer_remote(self, *_):
        """for a remote user, should be their full username"""
        self.assertEqual(
            utilities.get_user_identifier(self.remote_user), "rat@example.com"
        )

    def test_get_uuid(self, *_):
        """uuid functionality"""
        uuid = utilities.get_uuid("hi")
        self.assertTrue(re.match(r"hi[A-Za-z0-9\-]", uuid))

    def test_get_title(self, *_):
        """the title of a book"""
        self.assertEqual(utilities.get_title(None), "")
        self.assertEqual(utilities.get_title(self.book), "Test Book")
        book = models.Edition.objects.create(title="Oh", subtitle="oh my")
        self.assertEqual(utilities.get_title(book), "Oh: oh my")
