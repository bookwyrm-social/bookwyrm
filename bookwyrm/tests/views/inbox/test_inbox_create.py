""" tests incoming activities"""
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitySerializerError


class TransactionInboxCreate(TransactionTestCase):
    """readthrough tests"""

    def setUp(self):
        """basic user and book data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
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

        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    def test_create_status_transaction(self, *_):
        """the "it justs works" mode"""
        datafile = pathlib.Path(__file__).parent.joinpath(
            "../../data/ap_quotation.json"
        )
        status_data = json.loads(datafile.read_bytes())

        models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            views.inbox.activity_task(activity)
        self.assertEqual(mock.call_count, 0)


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
class InboxCreate(TestCase):
    """readthrough tests"""

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

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }

    def test_create_status(self, *_):
        """the "it justs works" mode"""
        datafile = pathlib.Path(__file__).parent.joinpath(
            "../../data/ap_quotation.json"
        )
        status_data = json.loads(datafile.read_bytes())

        models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = status_data

        views.inbox.activity_task(activity)

        status = models.Quotation.objects.get()
        self.assertEqual(
            status.remote_id, "https://example.com/user/mouse/quotation/13"
        )
        self.assertEqual(status.quote, "quote body")
        self.assertEqual(status.content, "commentary")
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.thread_id, status.id)

        # while we're here, lets ensure we avoid dupes
        views.inbox.activity_task(activity)
        self.assertEqual(models.Status.objects.count(), 1)

    def test_create_comment_with_reading_status(self, *_):
        """the "it justs works" mode"""
        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_comment.json")
        status_data = json.loads(datafile.read_bytes())
        status_data["readingStatus"] = "to-read"

        models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = status_data

        views.inbox.activity_task(activity)

        status = models.Comment.objects.get()
        self.assertEqual(status.remote_id, "https://example.com/user/mouse/comment/6")
        self.assertEqual(status.content, "commentary")
        self.assertEqual(status.reading_status, "to-read")
        self.assertEqual(status.user, self.local_user)

        # while we're here, lets ensure we avoid dupes
        views.inbox.activity_task(activity)
        self.assertEqual(models.Status.objects.count(), 1)

    def test_create_status_remote_note_with_mention(self, *_):
        """should only create it under the right circumstances"""
        self.assertFalse(
            models.Notification.objects.filter(user=self.local_user).exists()
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        activity = self.create_json
        activity["object"] = status_data

        views.inbox.activity_task(activity)

        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.mention_users.first(), self.local_user)
        self.assertTrue(
            models.Notification.objects.filter(user=self.local_user).exists()
        )
        self.assertEqual(models.Notification.objects.get().notification_type, "MENTION")

    def test_create_status_remote_note_with_reply(self, *_):
        """should only create it under the right circumstances"""
        parent_status = models.Status.objects.create(
            user=self.local_user,
            content="Test status",
            remote_id="https://example.com/status/1",
        )

        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(models.Notification.objects.filter(user=self.local_user))

        datafile = pathlib.Path(__file__).parent.joinpath("../../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        del status_data["tag"]
        status_data["inReplyTo"] = parent_status.remote_id
        activity = self.create_json
        activity["object"] = status_data

        views.inbox.activity_task(activity)
        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.reply_parent, parent_status)
        self.assertEqual(status.thread_id, parent_status.id)
        self.assertTrue(models.Notification.objects.filter(user=self.local_user))
        self.assertEqual(models.Notification.objects.get().notification_type, "REPLY")

    def test_create_rating(self, *_):
        """a remote rating activity"""
        book = models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/user/mouse/reviewrating/12",
            "type": "Rating",
            "published": "2021-04-29T21:27:30.014235+00:00",
            "attributedTo": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "replies": {
                "id": "https://example.com/user/mouse/reviewrating/12/replies",
                "type": "OrderedCollection",
                "totalItems": 0,
                "first": "https://example.com/u/mouse/reviewrating/12/replies?page=1",
                "last": "https://example.com/u/mouse/reviewrating/12/replies?page=1",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
            "inReplyTo": "",
            "summary": "",
            "tag": [],
            "attachment": [],
            "sensitive": False,
            "inReplyToBook": "https://example.com/book/1",
            "rating": 3,
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        rating = models.ReviewRating.objects.first()
        self.assertEqual(rating.book, book)
        self.assertEqual(rating.rating, 3.0)

    def test_create_list(self, *_):
        """a new list"""
        activity = self.create_json
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
        views.inbox.activity_task(activity)
        book_list = models.List.objects.get()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")

    def test_create_unsupported_type_question(self, *_):
        """ignore activities we know we can't handle"""
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/status/887",
            "type": "Question",
        }
        # just observe how it doesn't throw an error
        views.inbox.activity_task(activity)

    def test_create_unsupported_type_article(self, *_):
        """special case in unsupported type because we do know what it is"""
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/status/887",
            "type": "Article",
            "name": "hello",
            "published": "2021-04-29T21:27:30.014235+00:00",
            "attributedTo": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "sensitive": False,
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        # just observe how it doesn't throw an error
        views.inbox.activity_task(activity)

    def test_create_unsupported_type_unknown(self, *_):
        """Something truly unexpected should throw an error"""
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/status/887",
            "type": "Blaaaah",
        }
        # error this time
        with self.assertRaises(ActivitySerializerError):
            views.inbox.activity_task(activity)

    def test_create_unknown_type(self, *_):
        """ignore activities we know we've never heard of"""
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/status/887",
            "type": "Threnody",
        }
        with self.assertRaises(ActivitySerializerError):
            views.inbox.activity_task(activity)
