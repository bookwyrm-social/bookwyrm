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
        work = models.Work.objects.create(title="test work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_get_statuses_for_user_books(self, *_):
        """create a stream for a user"""
        alt_book = models.Edition.objects.create(
            title="hi", parent_work=self.book.parent_work
        )
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        status = models.Comment.objects.create(
            user=self.remote_user, content="hi", privacy="public", book=alt_book
        )
        models.ShelfBook.objects.create(
            user=self.local_user,
            shelf=self.local_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        result = activitystreams.BooksStream().get_statuses_for_user(self.local_user)
        self.assertEqual(list(result), [status])
