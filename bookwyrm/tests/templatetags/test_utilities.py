""" style fixes and lookups for templates """
from collections import namedtuple
import re
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import utilities


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class UtilitiesTags(TestCase):
    """lotta different things here"""

    # pylint: disable=invalid-name
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
        self.author = models.Author.objects.create(name="Jessica", isni="4")
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_uuid(self, *_):
        """uuid functionality"""
        uuid = utilities.get_uuid("hi")
        self.assertTrue(re.match(r"hi[A-Za-z0-9\-]", uuid))

    def test_join(self, *_):
        """concats things with underscores"""
        self.assertEqual(utilities.join("hi", 5, "blah", 0.75), "hi_5_blah_0.75")

    def test_get_user_identifer_local(self, *_):
        """fall back to the simplest uid available"""
        self.assertNotEqual(self.user.username, self.user.localname)
        self.assertEqual(utilities.get_user_identifier(self.user), "mouse")

    def test_get_user_identifer_remote(self, *_):
        """for a remote user, should be their full username"""
        self.assertEqual(
            utilities.get_user_identifier(self.remote_user), "rat@example.com"
        )

    def test_get_title(self, *_):
        """the title of a book"""
        self.assertEqual(utilities.get_title(None), "")
        self.assertEqual(utilities.get_title(self.book), "Test Book")
        book = models.Edition.objects.create(title="Oh", subtitle="oh my")
        self.assertEqual(utilities.get_title(book), "Oh: oh my")

    def test_comparison_bool(self, *_):
        """just a simple comparison"""
        self.assertTrue(utilities.comparison_bool("a", "a"))
        self.assertFalse(utilities.comparison_bool("a", "b"))

        self.assertFalse(utilities.comparison_bool("a", "a", reverse=True))
        self.assertTrue(utilities.comparison_bool("a", "b", reverse=True))

    def test_truncatepath(self, *_):
        """truncate a path"""
        ValueMock = namedtuple("Value", ("name"))
        value = ValueMock("home/one/two/three/four")
        self.assertEqual(utilities.truncatepath(value, 2), "home/…ur")
        self.assertEqual(utilities.truncatepath(value, "a"), "four")

    def test_get_isni_bio(self, *_):
        """get ISNI bio"""
        DataMock = namedtuple("Data", ("bio", "isni"))
        data = [DataMock(r"One\Dtwo", "4"), DataMock("Not used", "4")]

        result = utilities.get_isni_bio(data, self.author)
        self.assertEqual(result, "Author of <em>One\\Dtwo</em>")
