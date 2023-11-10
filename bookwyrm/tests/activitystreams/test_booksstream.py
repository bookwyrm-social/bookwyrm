""" testing activitystreams """
import itertools

from unittest.mock import patch
from django.test import TestCase
from bookwyrm import activitystreams, models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
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
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
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

    def test_book_statuses(self, *_):
        """statuses about a book"""
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

        class RedisMockCounter:
            """keep track of calls to mock redis store"""

            calls = []

            def bulk_add_objects_to_store(self, objs, store):
                """keep track of bulk_add_objects_to_store calls"""
                self.calls.append((objs, store))

        redis_mock_counter = RedisMockCounter()
        with patch(
            "bookwyrm.activitystreams.BooksStream.bulk_add_objects_to_store"
        ) as redis_mock:
            redis_mock.side_effect = redis_mock_counter.bulk_add_objects_to_store
            activitystreams.BooksStream().add_book_statuses(self.local_user, self.book)

        self.assertEqual(sum(map(lambda x: x[0].count(), redis_mock_counter.calls)), 1)
        self.assertTrue(
            status
            in itertools.chain.from_iterable(
                map(lambda x: x[0], redis_mock_counter.calls)
            )
        )
        for call in redis_mock_counter.calls:
            self.assertEqual(call[1], f"{self.local_user.id}-books")
