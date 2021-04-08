""" tests incoming activities"""
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxActivities(TestCase):
    """ inbox tests """

    def setUp(self):
        """ basic user and book data """
        self.local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False)
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

    def test_handle_add_book_to_shelf(self):
        """ shelving a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://bookwyrm.social/user/mouse/shelf/to-read"
        shelf.save()

        activity = {
            "id": "https://bookwyrm.social/shelfbook/6189#add",
            "type": "Add",
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
        self.assertEqual(shelf.books.first(), book)

    @responses.activate
    def test_handle_add_book_to_list(self):
        """ listing a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )

        responses.add(
            responses.GET,
            "https://bookwyrm.social/user/mouse/list/to-read",
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
            "id": "https://bookwyrm.social/listbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "ListItem",
                "book": self.edition.remote_id,
                "id": "https://bookwyrm.social/listbook/6189",
            },
            "target": "https://bookwyrm.social/user/mouse/list/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        booklist = models.List.objects.get()
        listitem = models.ListItem.objects.get()
        self.assertEqual(booklist.name, "Test List")
        self.assertEqual(booklist.books.first(), book)
        self.assertEqual(listitem.remote_id, "https://bookwyrm.social/listbook/6189")

    @responses.activate
    def test_handle_tag_book(self):
        """ listing a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )

        responses.add(
            responses.GET,
            "https://www.example.com/tag/cool-tag",
            json={
                "id": "https://1b1a78582461.ngrok.io/tag/tag",
                "type": "OrderedCollection",
                "totalItems": 0,
                "first": "https://1b1a78582461.ngrok.io/tag/tag?page=1",
                "last": "https://1b1a78582461.ngrok.io/tag/tag?page=1",
                "name": "cool tag",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        activity = {
            "id": "https://bookwyrm.social/listbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://www.example.com/tag/cool-tag",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        tag = models.Tag.objects.get()
        self.assertFalse(models.List.objects.exists())
        self.assertEqual(tag.name, "cool tag")
        self.assertEqual(tag.books.first(), book)
