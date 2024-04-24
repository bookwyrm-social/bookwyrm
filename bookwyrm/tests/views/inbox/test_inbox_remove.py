""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxRemove(TestCase):
    """inbox tests"""

    @classmethod
    def setUpTestData(cls):
        """basic user and book data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
            )
        cls.local_user.remote_id = "https://example.com/user/mouse"
        cls.local_user.save(broadcast=False, update_fields=["remote_id"])
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        cls.work = models.Work.objects.create(title="work title")
        cls.book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=cls.work,
        )

        models.SiteSettings.objects.create()

    def test_handle_unshelve_book(self):
        """remove a book from a shelf"""
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://bookwyrm.social/user/mouse/shelf/to-read"
        shelf.save()

        shelfbook = models.ShelfBook.objects.create(
            user=self.remote_user, shelf=shelf, book=self.book
        )

        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(shelf.books.count(), 1)

        activity = {
            "id": shelfbook.remote_id,
            "type": "Remove",
            "actor": "https://example.com/users/rat",
            "object": {
                "actor": self.remote_user.remote_id,
                "type": "ShelfItem",
                "book": self.book.remote_id,
                "id": shelfbook.remote_id,
            },
            "target": "https://bookwyrm.social/user/mouse/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        self.assertFalse(shelf.books.exists())

    def test_handle_remove_book_from_list(self):
        """listing a book"""
        with (
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
        ):
            booklist = models.List.objects.create(
                name="test list",
                user=self.local_user,
            )
            listitem = models.ListItem.objects.create(
                user=self.local_user,
                book=self.book,
                book_list=booklist,
                order=1,
            )
        self.assertEqual(booklist.books.count(), 1)

        activity = {
            "id": listitem.remote_id,
            "type": "Remove",
            "actor": "https://example.com/users/rat",
            "object": {
                "actor": self.remote_user.remote_id,
                "type": "ListItem",
                "book": self.book.remote_id,
                "id": listitem.remote_id,
            },
            "target": booklist.remote_id,
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        self.assertEqual(booklist.books.count(), 0)
