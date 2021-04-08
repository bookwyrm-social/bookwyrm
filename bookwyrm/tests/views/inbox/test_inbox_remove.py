""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxActivities(TestCase):
    """ inbox tests """

    def setUp(self):
        """ basic user and book data """
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

        models.SiteSettings.objects.create()

    def test_handle_unshelve_book(self):
        """ remove a book from a shelf """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://bookwyrm.social/user/mouse/shelf/to-read"
        shelf.save()

        shelfbook = models.ShelfBook.objects.create(
            user=self.remote_user, shelf=shelf, book=book
        )

        self.assertEqual(shelf.books.first(), book)
        self.assertEqual(shelf.books.count(), 1)

        activity = {
            "id": shelfbook.remote_id,
            "type": "Remove",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://bookwyrm.social/user/mouse/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        self.assertFalse(shelf.books.exists())
