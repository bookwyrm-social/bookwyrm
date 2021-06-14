""" tests incoming activities"""
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxUpdate(TestCase):
    """inbox tests"""

    def setUp(self):
        """basic user and book data"""
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

        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    def test_update_list(self):
        """a new list"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            book_list = models.List.objects.create(
                name="hi", remote_id="https://example.com/list/22", user=self.local_user
            )
        activity = {
            "type": "Update",
            "to": [],
            "cc": [],
            "actor": "hi",
            "id": "sdkjf",
            "object": {
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
        }
        views.inbox.activity_task(activity)
        book_list.refresh_from_db()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")

    def test_update_user(self):
        """update an existing user"""
        models.UserFollows.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        models.UserFollows.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
        )
        self.assertTrue(self.remote_user in self.local_user.followers.all())
        self.assertTrue(self.local_user in self.remote_user.followers.all())

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_user_rat.json")
        userdata = json.loads(datafile.read_bytes())
        del userdata["icon"]
        self.assertIsNone(self.remote_user.name)
        self.assertFalse(self.remote_user.discoverable)
        views.inbox.activity_task(
            {
                "type": "Update",
                "to": [],
                "cc": [],
                "actor": "hi",
                "id": "sdkjf",
                "object": userdata,
            }
        )
        user = models.User.objects.get(id=self.remote_user.id)
        self.assertEqual(user.name, "RAT???")
        self.assertEqual(user.username, "rat@example.com")
        self.assertTrue(user.discoverable)

        # make sure relationships aren't disrupted
        self.assertTrue(self.remote_user in self.local_user.followers.all())
        self.assertTrue(self.local_user in self.remote_user.followers.all())

    def test_update_edition(self):
        """update an existing edition"""
        datafile = pathlib.Path(__file__).parent.joinpath("../../data/bw_edition.json")
        bookdata = json.loads(datafile.read_bytes())

        models.Work.objects.create(
            title="Test Work", remote_id="https://bookwyrm.social/book/5988"
        )
        book = models.Edition.objects.create(
            title="Test Book", remote_id="https://bookwyrm.social/book/5989"
        )

        del bookdata["authors"]
        self.assertEqual(book.title, "Test Book")

        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            views.inbox.activity_task(
                {
                    "type": "Update",
                    "to": [],
                    "cc": [],
                    "actor": "hi",
                    "id": "sdkjf",
                    "object": bookdata,
                }
            )
        book = models.Edition.objects.get(id=book.id)
        self.assertEqual(book.title, "Piranesi")
        self.assertEqual(book.last_edited_by, self.remote_user)

    def test_update_work(self):
        """update an existing edition"""
        datafile = pathlib.Path(__file__).parent.joinpath("../../data/bw_work.json")
        bookdata = json.loads(datafile.read_bytes())

        book = models.Work.objects.create(
            title="Test Book", remote_id="https://bookwyrm.social/book/5988"
        )

        del bookdata["authors"]
        self.assertEqual(book.title, "Test Book")
        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            views.inbox.activity_task(
                {
                    "type": "Update",
                    "to": [],
                    "cc": [],
                    "actor": "hi",
                    "id": "sdkjf",
                    "object": bookdata,
                }
            )
        book = models.Work.objects.get(id=book.id)
        self.assertEqual(book.title, "Piranesi")
