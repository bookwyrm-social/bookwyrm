""" testing model activitypub utilities """
from unittest.mock import patch
from collections import namedtuple
from dataclasses import dataclass
import re
from django import db
from django.test import TestCase

from bookwyrm.activitypub.base_activity import ActivityObject
from bookwyrm import models
from bookwyrm.models import base_model
from bookwyrm.models.activitypub_mixin import ActivitypubMixin
from bookwyrm.models.activitypub_mixin import ActivityMixin, ObjectMixin


@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class ActivitypubMixins(TestCase):
    """functionality shared across models"""

    def setUp(self):
        """shared data"""
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
        )
        self.local_user.remote_id = "http://example.com/a/b"
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

        self.object_mock = {
            "to": "to field",
            "cc": "cc field",
            "content": "hi",
            "id": "bip",
            "type": "Test",
            "published": "2020-12-04T17:52:22.623807+00:00",
        }

    # ActivitypubMixin
    def test_to_activity(self, _):
        """model to ActivityPub json"""

        @dataclass(init=False)
        class TestActivity(ActivityObject):
            """real simple mock"""

            type: str = "Test"

        class TestModel(ActivitypubMixin, base_model.BookWyrmModel):
            """real simple mock model because BookWyrmModel is abstract"""

        instance = TestModel()
        instance.remote_id = "https://www.example.com/test"
        instance.activity_serializer = TestActivity

        activity = instance.to_activity()
        self.assertIsInstance(activity, dict)
        self.assertEqual(activity["id"], "https://www.example.com/test")
        self.assertEqual(activity["type"], "Test")

    def test_find_existing_by_remote_id(self, _):
        """attempt to match a remote id to an object in the db"""
        # uses a different remote id scheme
        # this isn't really part of this test directly but it's helpful to state
        book = models.Edition.objects.create(
            title="Test Edition", remote_id="http://book.com/book"
        )

        self.assertEqual(book.origin_id, "http://book.com/book")
        self.assertNotEqual(book.remote_id, "http://book.com/book")

        # uses subclasses
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.Comment.objects.create(
                user=self.local_user,
                content="test status",
                book=book,
                remote_id="https://comment.net",
            )

        result = models.User.find_existing_by_remote_id("hi")
        self.assertIsNone(result)

        result = models.User.find_existing_by_remote_id("http://example.com/a/b")
        self.assertEqual(result, self.local_user)

        # test using origin id
        result = models.Edition.find_existing_by_remote_id("http://book.com/book")
        self.assertEqual(result, book)

        # test subclass match
        result = models.Status.find_existing_by_remote_id("https://comment.net")

    def test_find_existing(self, _):
        """match a blob of data to a model"""
        book = models.Edition.objects.create(
            title="Test edition",
            openlibrary_key="OL1234",
        )

        result = models.Edition.find_existing({"openlibraryKey": "OL1234"})
        self.assertEqual(result, book)

    def test_get_recipients_public_object(self, _):
        """determines the recipients for an object's broadcast"""
        MockSelf = namedtuple("Self", ("privacy"))
        mock_self = MockSelf("public")
        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], self.remote_user.inbox)

    def test_get_recipients_public_user_object_no_followers(self, _):
        """determines the recipients for a user's object broadcast"""
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 0)

    def test_get_recipients_public_user_object(self, _):
        """determines the recipients for a user's object broadcast"""
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)
        self.local_user.followers.add(self.remote_user)

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], self.remote_user.inbox)

    def test_get_recipients_public_user_object_with_mention(self, _):
        """determines the recipients for a user's object broadcast"""
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)
        self.local_user.followers.add(self.remote_user)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            another_remote_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.com",
                "nutriaword",
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                outbox="https://example.com/users/nutria/outbox",
            )
        MockSelf = namedtuple("Self", ("privacy", "user", "recipients"))
        mock_self = MockSelf("public", self.local_user, [another_remote_user])

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 2)
        self.assertTrue(another_remote_user.inbox in recipients)
        self.assertTrue(self.remote_user.inbox in recipients)

    def test_get_recipients_direct(self, _):
        """determines the recipients for a user's object broadcast"""
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)
        self.local_user.followers.add(self.remote_user)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            another_remote_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.com",
                "nutriaword",
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                outbox="https://example.com/users/nutria/outbox",
            )
        MockSelf = namedtuple("Self", ("privacy", "user", "recipients"))
        mock_self = MockSelf("direct", self.local_user, [another_remote_user])

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], another_remote_user.inbox)

    def test_get_recipients_combine_inboxes(self, _):
        """should combine users with the same shared_inbox"""
        self.remote_user.shared_inbox = "http://example.com/inbox"
        self.remote_user.save(broadcast=False)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            another_remote_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.com",
                "nutriaword",
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                shared_inbox="http://example.com/inbox",
                outbox="https://example.com/users/nutria/outbox",
            )
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)
        self.local_user.followers.add(self.remote_user)
        self.local_user.followers.add(another_remote_user)

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], "http://example.com/inbox")

    def test_get_recipients_software(self, _):
        """should differentiate between bookwyrm and other remote users"""
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            another_remote_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.com",
                "nutriaword",
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                outbox="https://example.com/users/nutria/outbox",
                bookwyrm_user=False,
            )
        MockSelf = namedtuple("Self", ("privacy", "user"))
        mock_self = MockSelf("public", self.local_user)
        self.local_user.followers.add(self.remote_user)
        self.local_user.followers.add(another_remote_user)

        recipients = ActivitypubMixin.get_recipients(mock_self)
        self.assertEqual(len(recipients), 2)

        recipients = ActivitypubMixin.get_recipients(mock_self, software="bookwyrm")
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], self.remote_user.inbox)

        recipients = ActivitypubMixin.get_recipients(mock_self, software="other")
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0], another_remote_user.inbox)

    # ObjectMixin
    def test_object_save_create(self, _):
        """should save uneventufully when broadcast is disabled"""

        class Success(Exception):
            """this means we got to the right method"""

        class ObjectModel(ObjectMixin, base_model.BookWyrmModel):
            """real simple mock model because BookWyrmModel is abstract"""

            user = models.fields.ForeignKey("User", on_delete=db.models.CASCADE)

            def save(self, *args, **kwargs):
                with patch("django.db.models.Model.save"):
                    super().save(*args, **kwargs)

            def broadcast(
                self, activity, sender, **kwargs
            ):  # pylint: disable=arguments-differ
                """do something"""
                raise Success()

            def to_create_activity(self, user):  # pylint: disable=arguments-differ
                return {}

        with self.assertRaises(Success):
            ObjectModel(user=self.local_user).save()

        ObjectModel(user=self.remote_user).save()
        ObjectModel(user=self.local_user).save(broadcast=False)
        ObjectModel(user=None).save()

    def test_object_save_update(self, _):
        """should save uneventufully when broadcast is disabled"""

        class Success(Exception):
            """this means we got to the right method"""

        class UpdateObjectModel(ObjectMixin, base_model.BookWyrmModel):
            """real simple mock model because BookWyrmModel is abstract"""

            user = models.fields.ForeignKey("User", on_delete=db.models.CASCADE)
            last_edited_by = models.fields.ForeignKey(
                "User", on_delete=db.models.CASCADE
            )

            def save(self, *args, **kwargs):
                with patch("django.db.models.Model.save"):
                    super().save(*args, **kwargs)

            def to_update_activity(self, user):
                raise Success()

        with self.assertRaises(Success):
            UpdateObjectModel(id=1, user=self.local_user).save()
        with self.assertRaises(Success):
            UpdateObjectModel(id=1, last_edited_by=self.local_user).save()

    def test_object_save_delete(self, _):
        """should create delete activities when objects are deleted by flag"""

        class ActivitySuccess(Exception):
            """this means we got to the right method"""

        class DeletableObjectModel(ObjectMixin, base_model.BookWyrmModel):
            """real simple mock model because BookWyrmModel is abstract"""

            user = models.fields.ForeignKey("User", on_delete=db.models.CASCADE)
            deleted = models.fields.BooleanField()

            def save(self, *args, **kwargs):
                with patch("django.db.models.Model.save"):
                    super().save(*args, **kwargs)

            def to_delete_activity(self, user):
                raise ActivitySuccess()

        with self.assertRaises(ActivitySuccess):
            DeletableObjectModel(id=1, user=self.local_user, deleted=True).save()

    def test_to_delete_activity(self, _):
        """wrapper for Delete activity"""
        MockSelf = namedtuple("Self", ("remote_id", "to_activity"))
        mock_self = MockSelf(
            "https://example.com/status/1", lambda *args: self.object_mock
        )
        activity = ObjectMixin.to_delete_activity(mock_self, self.local_user)
        self.assertEqual(activity["id"], "https://example.com/status/1/activity")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["to"], ["%s/followers" % self.local_user.remote_id])
        self.assertEqual(
            activity["cc"], ["https://www.w3.org/ns/activitystreams#Public"]
        )

    def test_to_update_activity(self, _):
        """ditto above but for Update"""
        MockSelf = namedtuple("Self", ("remote_id", "to_activity"))
        mock_self = MockSelf(
            "https://example.com/status/1", lambda *args: self.object_mock
        )
        activity = ObjectMixin.to_update_activity(mock_self, self.local_user)
        self.assertIsNotNone(
            re.match(r"^https:\/\/example\.com\/status\/1#update\/.*", activity["id"])
        )
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(
            activity["to"], ["https://www.w3.org/ns/activitystreams#Public"]
        )
        self.assertIsInstance(activity["object"], dict)

    # Activity mixin
    def test_to_undo_activity(self, _):
        """and again, for Undo"""
        MockSelf = namedtuple("Self", ("remote_id", "to_activity", "user"))
        mock_self = MockSelf(
            "https://example.com/status/1",
            lambda *args: self.object_mock,
            self.local_user,
        )
        activity = ActivityMixin.to_undo_activity(mock_self)
        self.assertEqual(activity["id"], "https://example.com/status/1#undo")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["type"], "Undo")
        self.assertIsInstance(activity["object"], dict)
