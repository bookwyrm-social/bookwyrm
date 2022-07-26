""" testing lists_stream """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import lists_stream, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class ListsStreamSignals(TestCase):
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
                "fish", "fish@fish.fish", "password", local=True, localname="fish"
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

    def test_add_list_on_create_command(self, _):
        """a new lists has entered"""
        with patch("bookwyrm.lists_stream.remove_list_task.delay"):
            book_list = models.List.objects.create(
                user=self.remote_user, name="hi", privacy="public"
            )
        with patch("bookwyrm.lists_stream.add_list_task.delay") as mock:
            lists_stream.add_list_on_create_command(book_list.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], book_list.id)

    def test_remove_list_on_delete(self, _):
        """delete a list"""
        with patch("bookwyrm.lists_stream.remove_list_task.delay"):
            book_list = models.List.objects.create(
                user=self.remote_user, name="hi", privacy="public"
            )
        with patch("bookwyrm.lists_stream.remove_list_task.delay") as mock:
            lists_stream.remove_list_on_delete(models.List, book_list)
        args = mock.call_args[0]
        self.assertEqual(args[0], book_list.id)

    def test_populate_lists_on_account_create_command(self, _):
        """create streams for a user"""
        with patch("bookwyrm.lists_stream.populate_lists_task.delay") as mock:
            lists_stream.add_list_on_account_create_command(self.local_user.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    def test_remove_lists_on_block(self, *_):
        """don't show lists from blocked users"""
        with patch("bookwyrm.lists_stream.remove_user_lists_task.delay") as mock:
            models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    @patch("bookwyrm.activitystreams.add_user_statuses_task.delay")
    def test_add_lists_on_unblock(self, *_):
        """re-add lists on unblock"""
        with patch("bookwyrm.lists_stream.remove_user_lists_task.delay"):
            block = models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        with patch("bookwyrm.lists_stream.add_user_lists_task.delay") as mock:
            block.delete()

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    @patch("bookwyrm.activitystreams.remove_user_statuses_task.delay")
    @patch("bookwyrm.activitystreams.add_user_statuses_task.delay")
    def test_add_lists_on_unblock_reciprocal_block(self, *_):
        """dont' re-add lists on unblock if there's a block the other way"""
        with patch("bookwyrm.lists_stream.remove_user_lists_task.delay"):
            block = models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )
            block = models.UserBlocks.objects.create(
                user_subject=self.remote_user,
                user_object=self.local_user,
            )

        with patch("bookwyrm.lists_stream.add_user_lists_task.delay") as mock:
            block.delete()

        self.assertFalse(mock.called)
