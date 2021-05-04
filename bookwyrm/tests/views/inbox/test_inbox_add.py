""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxAdd(TestCase):
    """inbox tests"""

    def setUp(self):
        """basic user and book data"""
        local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        local_user.remote_id = "https://example.com/user/mouse"
        local_user.save(broadcast=False)
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
        work = models.Work.objects.create(title="work title")
        self.book = models.Edition.objects.create(
            title="Test",
            remote_id="https://example.com/book/37292",
            parent_work=work,
        )

        models.SiteSettings.objects.create()

    @responses.activate
    def test_handle_add_book_to_shelf(self):
        """shelving a book"""
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://example.com/user/rat/shelf/to-read"
        shelf.save()

        responses.add(
            responses.GET,
            "https://example.com/user/rat/shelf/to-read",
            json={
                "id": shelf.remote_id,
                "type": "Shelf",
                "totalItems": 1,
                "first": "https://example.com/shelf/22?page=1",
                "last": "https://example.com/shelf/22?page=1",
                "name": "Test Shelf",
                "owner": self.remote_user.remote_id,
                "to": ["https://www.w3.org/ns/activitystreams#Public"],
                "cc": ["https://example.com/user/rat/followers"],
                "summary": "summary text",
                "curation": "curated",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        activity = {
            "id": "https://example.com/shelfbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "actor": self.remote_user.remote_id,
                "type": "ShelfItem",
                "book": self.book.remote_id,
                "id": "https://example.com/shelfbook/6189",
            },
            "target": "https://example.com/user/rat/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        self.assertEqual(shelf.books.first(), self.book)

    @responses.activate
    def test_handle_add_book_to_list(self):
        """listing a book"""
        responses.add(
            responses.GET,
            "https://example.com/user/mouse/list/to-read",
            json={
                "id": "https://example.com/list/22",
                "type": "BookList",
                "totalItems": 1,
                "first": "https://example.com/list/22?page=1",
                "last": "https://example.com/list/22?page=1",
                "name": "Test List",
                "owner": "https://example.com/user/mouse",
                "to": ["https://www.w3.org/ns/activitystreams#Public"],
                "cc": ["https://example.com/user/mouse/followers"],
                "summary": "summary text",
                "curation": "curated",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        activity = {
            "id": "https://example.com/listbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "actor": self.remote_user.remote_id,
                "type": "ListItem",
                "book": self.book.remote_id,
                "id": "https://example.com/listbook/6189",
                "order": 1,
            },
            "target": "https://example.com/user/mouse/list/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        booklist = models.List.objects.get()
        listitem = models.ListItem.objects.get()
        self.assertEqual(booklist.name, "Test List")
        self.assertEqual(booklist.books.first(), self.book)
        self.assertEqual(listitem.remote_id, "https://example.com/listbook/6189")
