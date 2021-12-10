""" testing activitystreams """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import lists_stream, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class ListsStream(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
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
        self.stream = lists_stream.ListsStream()

    def test_lists_stream_ids(self, *_):
        """the abstract base class for stream objects"""
        self.assertEqual(
            self.stream.stream_id(self.local_user),
            f"{self.local_user.id}-lists",
        )

    def test_get_audience(self, *_):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        users = self.stream.get_audience(book_list)
        # remote users don't have feeds
        self.assertFalse(self.remote_user in users)
        self.assertTrue(self.local_user in users)
        self.assertTrue(self.another_user in users)

    def test_get_audience_direct(self, *_):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(users.exists())

        book_list = models.List.objects.create(
            user=self.local_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
        self.assertFalse(self.remote_user in users)

    def test_get_audience_followers_remote_user(self, *_):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="followers",
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(users.exists())

    def test_get_audience_followers_self(self, *_):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.local_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
        self.assertFalse(self.remote_user in users)

    def test_get_audience_followers_with_relationship(self, *_):
        """get a list of users that should see a list"""
        self.remote_user.followers.add(self.local_user)
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(self.local_user in users)
        self.assertFalse(self.another_user in users)
        self.assertFalse(self.remote_user in users)
