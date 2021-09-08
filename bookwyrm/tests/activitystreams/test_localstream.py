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
        work = models.Work.objects.create(title="test work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_localstream_get_audience_remote_status(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertEqual(users, [])

    def test_localstream_get_audience_local_status(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertTrue(self.local_user in users)
        self.assertTrue(self.another_user in users)

    def test_localstream_get_audience_unlisted(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="unlisted"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertEqual(users, [])

    def test_localstream_get_audience_books_no_book(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        audience = activitystreams.BooksStream().get_audience(status)
        # no books, no audience
        self.assertEqual(audience, [])

    def test_localstream_get_audience_books_mention_books(self, *_):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        status.mention_books.add(self.book)
        status.save(broadcast=False)
        models.ShelfBook.objects.create(
            user=self.local_user,
            shelf=self.local_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.local_user in audience)

    def test_localstream_get_audience_books_book_field(self, *_):
        """get a list of users that should see a status"""
        status = models.Comment.objects.create(
            user=self.local_user, content="hi", privacy="public", book=self.book
        )
        models.ShelfBook.objects.create(
            user=self.local_user,
            shelf=self.local_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.local_user in audience)

    def test_localstream_get_audience_books_alternate_edition(self, *_):
        """get a list of users that should see a status"""
        alt_book = models.Edition.objects.create(
            title="hi", parent_work=self.book.parent_work
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
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.local_user in audience)

    def test_localstream_get_audience_books_non_public(self, *_):
        """get a list of users that should see a status"""
        alt_book = models.Edition.objects.create(
            title="hi", parent_work=self.book.parent_work
        )
        status = models.Comment.objects.create(
            user=self.remote_user, content="hi", privacy="unlisted", book=alt_book
        )
        models.ShelfBook.objects.create(
            user=self.local_user,
            shelf=self.local_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertEqual(audience, [])
