""" testing user follow suggestions """
from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models
from bookwyrm.suggested_users import suggested_users


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class SuggestedUsers(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )
        self.book = models.Edition.objects.create(title="test book")

    def test_get_rank(self, *_):
        """a float that reflects both the mutuals count and shared books"""
        Mock = namedtuple("AnnotatedUserMock", ("mutuals", "shared_books"))
        annotated_user_mock = Mock(3, 27)
        rank = suggested_users.get_rank(annotated_user_mock)
        self.assertEqual(rank, 3.9642857142857144)

    def test_store_id(self, *_):
        """redis key generation"""
        self.assertEqual(
            suggested_users.store_id(self.local_user),
            "{:d}-suggestions".format(self.local_user.id),
        )

    def test_get_counts_from_rank(self, *_):
        """reverse the rank computation to get the mutuals and shared books counts"""
        counts = suggested_users.get_counts_from_rank(3.9642857142857144)
        self.assertEqual(counts["mutuals"], 3)
        self.assertEqual(counts["shared_books"], 27)

    def test_get_objects_for_store(self, *_):
        """list of people to follow for a given user"""

        mutual_user = models.User.objects.create_user(
            "rat", "rat@local.rat", "password", local=True, localname="rat"
        )
        suggestable_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
            discoverable=True,
        )

        # you follow rat
        mutual_user.followers.add(self.local_user)
        # rat follows the suggested user
        suggestable_user.followers.add(mutual_user)

        results = suggested_users.get_objects_for_store(
            "{:d}-suggestions".format(self.local_user.id)
        )
        self.assertEqual(results.count(), 1)
        match = results.first()
        self.assertEqual(match.id, suggestable_user.id)
        self.assertEqual(match.mutuals, 1)

    def test_create_user_signal(self, *_):
        """build suggestions for new users"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay") as mock:
            models.User.objects.create_user(
                "nutria", "nutria@nu.tria", "password", local=True, localname="nutria"
            )

        self.assertEqual(mock.call_count, 1)
