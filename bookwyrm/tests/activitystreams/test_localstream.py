"""testing activitystreams"""

from django.test import TestCase
from bookwyrm import activitystreams, models


class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """use a test csv"""
        cls.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        cls.another_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
        )
        cls.remote_user = models.User.objects.create_user(
            "rat",
            "rat@rat.com",
            "ratword",
            local=False,
            remote_id="https://example.com/users/rat",
            inbox="https://example.com/users/rat/inbox",
            outbox="https://example.com/users/rat/outbox",
        )
        work = models.Work.objects.create(title="test work")
        cls.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_localstream_get_audience_remote_status(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertEqual(users, [])

    def test_localstream_get_audience_local_status(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertFalse(self.local_user.id in users)
        self.assertTrue(self.another_user.id in users)

    def test_localstream_get_audience_unlisted(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="unlisted"
        )
        users = activitystreams.LocalStream().get_audience(status)
        self.assertEqual(users, [])

    def test_bookstream_get_audience_books_no_book(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        models.ShelfBook.objects.create(
            user=self.local_user,
            shelf=self.local_user.shelf_set.first(),
            book=self.book,
        )
        audience = activitystreams.BooksStream().get_audience(status)
        # no books, no audience
        self.assertEqual(audience, [])

    def test_bookstream_get_audience_books_mention_books(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.local_user, content="hi", privacy="public"
        )
        status.mention_books.add(self.book)
        status.save(broadcast=False)
        models.ShelfBook.objects.create(
            user=self.another_user,
            shelf=self.another_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.another_user.id in audience)

    def test_bookstream_get_audience_books_book_field(self):
        """get a list of users that should see a status"""
        status = models.Comment.objects.create(
            user=self.local_user, content="hi", privacy="public", book=self.book
        )
        models.ShelfBook.objects.create(
            user=self.another_user,
            shelf=self.another_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, no audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.another_user.id in audience)

    def test_bookstream_get_audience_books_alternate_edition(self):
        """get a list of users that should see a status"""
        alt_book = models.Edition.objects.create(
            title="hi", parent_work=self.book.parent_work
        )
        status = models.Comment.objects.create(
            user=self.remote_user, content="hi", privacy="public", book=alt_book
        )
        models.ShelfBook.objects.create(
            user=self.another_user,
            shelf=self.another_user.shelf_set.first(),
            book=self.book,
        )
        # yes book, yes audience
        audience = activitystreams.BooksStream().get_audience(status)
        self.assertTrue(self.another_user.id in audience)

    def test_bookstream_get_audience_books_non_public(self):
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
