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
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
            )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False, update_fields=["remote_id"])
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

        self.update_json = {
            "id": "hi",
            "type": "Update",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }

        models.SiteSettings.objects.create()

    def test_update_list(self):
        """a new list"""
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.lists_stream.remove_list_task.delay"):
            book_list = models.List.objects.create(
                name="hi", remote_id="https://example.com/list/22", user=self.local_user
            )
        activity = self.update_json
        activity["object"] = {
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
        }
        with patch("bookwyrm.lists_stream.remove_list_task.delay"):
            views.inbox.activity_task(activity)
        book_list.refresh_from_db()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")

    @patch("bookwyrm.suggested_users.rerank_user_task.delay")
    @patch("bookwyrm.activitystreams.add_user_statuses_task.delay")
    @patch("bookwyrm.lists_stream.add_user_lists_task.delay")
    def test_update_user(self, *_):
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

    def test_update_edition_links(self):
        """add links to edition"""
        datafile = pathlib.Path(__file__).parent.joinpath("../../data/bw_edition.json")
        bookdata = json.loads(datafile.read_bytes())
        del bookdata["authors"]
        # pylint: disable=line-too-long
        link_data = {
            "href": "https://openlibrary.org/books/OL11645413M/Queen_Victoria/daisy",
            "mediaType": "Daisy",
            "attributedTo": self.remote_user.remote_id,
        }
        bookdata["fileLinks"] = [link_data]

        models.Work.objects.create(
            title="Test Work", remote_id="https://bookwyrm.social/book/5988"
        )
        book = models.Edition.objects.create(
            title="Test Book", remote_id="https://bookwyrm.social/book/5989"
        )
        self.assertFalse(book.file_links.exists())

        with patch(
            "bookwyrm.activitypub.base_activity.set_related_field.delay"
        ) as mock:
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
        args = mock.call_args[0]
        self.assertEqual(args[0], "FileLink")
        self.assertEqual(args[1], "Edition")
        self.assertEqual(args[2], "book")
        self.assertEqual(args[3], book.remote_id)
        self.assertEqual(args[4], link_data)
        # idk how to test that related name works, because of the transaction

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

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_update_status(self, *_):
        """edit a status"""
        status = models.Status.objects.create(user=self.remote_user, content="hi")

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        status_data["id"] = status.remote_id
        status_data["updated"] = "2021-12-13T05:09:29Z"

        activity = self.update_json
        activity["object"] = status_data

        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            views.inbox.activity_task(activity)

        status.refresh_from_db()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.edited_date.year, 2021)
        self.assertEqual(status.edited_date.month, 12)
        self.assertEqual(status.edited_date.day, 13)
