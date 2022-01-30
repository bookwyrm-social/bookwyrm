""" testing models """
from unittest.mock import patch
from io import BytesIO
import pathlib
import re

from django.http import Http404
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone
from PIL import Image
import responses

from bookwyrm import activitypub, models, settings


# pylint: disable=too-many-public-methods
# pylint: disable=line-too-long
@patch("bookwyrm.models.Status.broadcast")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.remove_status_task.delay")
class Status(TestCase):
    """lotta types of statuses"""

    def setUp(self):
        """useful things for creating a status"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
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
        self.book = models.Edition.objects.create(title="Test Edition")

        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        with patch("bookwyrm.models.Status.broadcast"):
            image.save(output, format=image.format)
            self.book.cover.save("test.jpg", ContentFile(output.getvalue()))

        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_status_generated_fields(self, *_):
        """setting remote id"""
        status = models.Status.objects.create(content="bleh", user=self.local_user)
        expected_id = f"https://{settings.DOMAIN}/user/mouse/status/{status.id}"
        self.assertEqual(status.remote_id, expected_id)
        self.assertEqual(status.privacy, "public")

    def test_replies(self, *_):
        """get a list of replies"""
        parent = models.Status(content="hi", user=self.local_user)
        parent.save(broadcast=False)
        child = models.Status(
            content="hello", reply_parent=parent, user=self.local_user
        )
        child.save(broadcast=False)
        sibling = models.Review(
            content="hey", reply_parent=parent, user=self.local_user, book=self.book
        )
        sibling.save(broadcast=False)
        grandchild = models.Status(
            content="hi hello", reply_parent=child, user=self.local_user
        )
        grandchild.save(broadcast=False)

        replies = models.Status.replies(parent)
        self.assertEqual(replies.count(), 2)
        self.assertEqual(replies.first(), child)
        # should select subclasses
        self.assertIsInstance(replies.last(), models.Review)

        self.assertEqual(parent.thread_id, parent.id)
        self.assertEqual(child.thread_id, parent.id)
        self.assertEqual(sibling.thread_id, parent.id)
        self.assertEqual(grandchild.thread_id, parent.id)

    def test_status_type(self, *_):
        """class name"""
        self.assertEqual(models.Status().status_type, "Note")
        self.assertEqual(models.Review().status_type, "Review")
        self.assertEqual(models.Quotation().status_type, "Quotation")
        self.assertEqual(models.Comment().status_type, "Comment")
        self.assertEqual(models.Boost().status_type, "Announce")

    def test_boostable(self, *_):
        """can a status be boosted, based on privacy"""
        self.assertTrue(models.Status(privacy="public").boostable)
        self.assertTrue(models.Status(privacy="unlisted").boostable)
        self.assertFalse(models.Status(privacy="followers").boostable)
        self.assertFalse(models.Status(privacy="direct").boostable)

    def test_to_replies(self, *_):
        """activitypub replies collection"""
        parent = models.Status.objects.create(content="hi", user=self.local_user)
        child = models.Status.objects.create(
            content="hello", reply_parent=parent, user=self.local_user
        )
        models.Review.objects.create(
            content="hey", reply_parent=parent, user=self.local_user, book=self.book
        )
        models.Status.objects.create(
            content="hi hello", reply_parent=child, user=self.local_user
        )

        replies = parent.to_replies()
        self.assertEqual(replies["id"], f"{parent.remote_id}/replies")
        self.assertEqual(replies["totalItems"], 2)

    def test_status_to_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Status.objects.create(
            content="test content", user=self.local_user
        )
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["sensitive"], False)

    def test_status_to_activity_tombstone(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Status.objects.create(
            content="test content",
            user=self.local_user,
            deleted=True,
            deleted_date=timezone.now(),
        )
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Tombstone")
        self.assertFalse(hasattr(activity, "content"))

    def test_status_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Status.objects.create(
            content="test content", user=self.local_user
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["sensitive"], False)
        self.assertEqual(activity["attachment"], [])

    def test_generated_note_to_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.GeneratedNote.objects.create(
            content="test content", user=self.local_user
        )
        status.mention_books.set([self.book])
        status.mention_users.set([self.local_user])
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "GeneratedNote")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["sensitive"], False)
        self.assertEqual(len(activity["tag"]), 2)

    def test_generated_note_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.GeneratedNote.objects.create(
            content="test content", user=self.local_user
        )
        status.mention_books.set([self.book])
        status.mention_users.set([self.local_user])
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(
            activity["content"],
            f'mouse test content <a href="{self.book.remote_id}">"Test Edition"</a>',
        )
        self.assertEqual(len(activity["tag"]), 2)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(activity["sensitive"], False)
        self.assertIsInstance(activity["attachment"], list)
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_comment_to_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Comment.objects.create(
            content="test content", user=self.local_user, book=self.book
        )
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Comment")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["inReplyToBook"], self.book.remote_id)

    def test_comment_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Comment.objects.create(
            content="test content", user=self.local_user, book=self.book
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(
            activity["content"],
            f'test content<p>(comment on <a href="{self.book.remote_id}">"Test Edition"</a>)</p>',
        )
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_quotation_to_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Quotation")
        self.assertEqual(activity["quote"], "a sickening sense")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["inReplyToBook"], self.book.remote_id)

    def test_quotation_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(
            activity["content"],
            f'a sickening sense <p>-- <a href="{self.book.remote_id}">"Test Edition"</a></p>test content',
        )
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_review_to_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3.0,
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity()
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Review")
        self.assertEqual(activity["rating"], 3)
        self.assertEqual(activity["name"], "Review name")
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["inReplyToBook"], self.book.remote_id)

    def test_review_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Review.objects.create(
            name="Review's name",
            content="test content",
            rating=3.0,
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Article")
        self.assertEqual(
            activity["name"],
            f'Review of "{self.book.title}" (3 stars): Review\'s name',
        )
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_review_to_pure_activity_no_rating(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.Review.objects.create(
            name="Review name",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Article")
        self.assertEqual(
            activity["name"],
            f'Review of "{self.book.title}": Review name',
        )
        self.assertEqual(activity["content"], "test content")
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_reviewrating_to_pure_activity(self, *_):
        """subclass of the base model version with a "pure" serializer"""
        status = models.ReviewRating.objects.create(
            rating=3.0,
            user=self.local_user,
            book=self.book,
        )
        activity = status.to_activity(pure=True)
        self.assertEqual(activity["id"], status.remote_id)
        self.assertEqual(activity["type"], "Note")
        self.assertEqual(
            activity["content"],
            f'rated <em><a href="{self.book.remote_id}">{self.book.title}</a></em>: 3 stars',
        )
        self.assertEqual(activity["attachment"][0].type, "Document")
        self.assertTrue(
            re.match(
                r"https:\/\/your.domain.here\/images\/covers\/test_[A-z0-9]+.jpg",
                activity["attachment"][0].url,
            )
        )
        self.assertEqual(activity["attachment"][0].name, "Test Edition")

    def test_favorite(self, *_):
        """fav a status"""
        status = models.Status.objects.create(
            content="test content", user=self.local_user
        )

        with patch("bookwyrm.models.Favorite.broadcast") as mock:
            fav = models.Favorite.objects.create(status=status, user=self.local_user)
        args = mock.call_args[0]
        self.assertEqual(args[1].remote_id, self.local_user.remote_id)
        self.assertEqual(args[0]["type"], "Like")

        # can't fav a status twice
        with self.assertRaises(IntegrityError):
            models.Favorite.objects.create(status=status, user=self.local_user)

        activity = fav.to_activity()
        self.assertEqual(activity["type"], "Like")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"], status.remote_id)

    def test_boost(self, *_):
        """boosting, this one's a bit fussy"""
        status = models.Status.objects.create(
            content="test content", user=self.local_user
        )
        boost = models.Boost.objects.create(boosted_status=status, user=self.local_user)
        activity = boost.to_activity()
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"], status.remote_id)
        self.assertEqual(activity["type"], "Announce")
        self.assertEqual(activity, boost.to_activity(pure=True))

    def test_notification(self, *_):
        """a simple model"""
        notification = models.Notification.objects.create(
            user=self.local_user, notification_type="FAVORITE"
        )
        self.assertFalse(notification.read)

        with self.assertRaises(IntegrityError):
            models.Notification.objects.create(
                user=self.local_user, notification_type="GLORB"
            )

    # pylint: disable=unused-argument
    def test_create_broadcast(self, one, two, broadcast_mock, *_):
        """should send out two verions of a status on create"""
        models.Comment.objects.create(
            content="hi", user=self.local_user, book=self.book
        )
        self.assertEqual(broadcast_mock.call_count, 2)
        pure_call = broadcast_mock.call_args_list[0]
        bw_call = broadcast_mock.call_args_list[1]

        self.assertEqual(pure_call[1]["software"], "other")
        args = pure_call[0][0]
        self.assertEqual(args["type"], "Create")
        self.assertEqual(args["object"]["type"], "Note")
        self.assertTrue("content" in args["object"])

        self.assertEqual(bw_call[1]["software"], "bookwyrm")
        args = bw_call[0][0]
        self.assertEqual(args["type"], "Create")
        self.assertEqual(args["object"]["type"], "Comment")

    def test_recipients_with_mentions(self, *_):
        """get recipients to broadcast a status"""
        status = models.GeneratedNote.objects.create(
            content="test content", user=self.local_user
        )
        status.mention_users.add(self.remote_user)

        self.assertEqual(status.recipients, [self.remote_user])

    def test_recipients_with_reply_parent(self, *_):
        """get recipients to broadcast a status"""
        parent_status = models.GeneratedNote.objects.create(
            content="test content", user=self.remote_user
        )
        status = models.GeneratedNote.objects.create(
            content="test content", user=self.local_user, reply_parent=parent_status
        )

        self.assertEqual(status.recipients, [self.remote_user])

    def test_recipients_with_reply_parent_and_mentions(self, *_):
        """get recipients to broadcast a status"""
        parent_status = models.GeneratedNote.objects.create(
            content="test content", user=self.remote_user
        )
        status = models.GeneratedNote.objects.create(
            content="test content", user=self.local_user, reply_parent=parent_status
        )
        status.mention_users.set([self.remote_user])

        self.assertEqual(status.recipients, [self.remote_user])

    @responses.activate
    def test_ignore_activity_boost(self, *_):
        """don't bother with most remote statuses"""
        activity = activitypub.Announce(
            id="http://www.faraway.com/boost/12",
            actor=self.remote_user.remote_id,
            object="http://fish.com/nothing",
            published="2021-03-24T18:59:41.841208+00:00",
            cc="",
            to="",
        )

        responses.add(responses.GET, "http://fish.com/nothing", status=404)

        self.assertTrue(models.Status.ignore_activity(activity))

    def test_raise_visible_to_user_public(self, *_):
        """privacy settings"""
        status = models.Status.objects.create(
            content="bleh", user=self.local_user, privacy="public"
        )
        self.assertIsNone(status.raise_visible_to_user(self.remote_user))
        self.assertIsNone(status.raise_visible_to_user(self.local_user))
        self.assertIsNone(status.raise_visible_to_user(self.anonymous_user))

    def test_raise_visible_to_user_unlisted(self, *_):
        """privacy settings"""
        status = models.Status.objects.create(
            content="bleh", user=self.local_user, privacy="unlisted"
        )
        self.assertIsNone(status.raise_visible_to_user(self.remote_user))
        self.assertIsNone(status.raise_visible_to_user(self.local_user))
        self.assertIsNone(status.raise_visible_to_user(self.anonymous_user))

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    def test_raise_visible_to_user_followers(self, *_):
        """privacy settings"""
        status = models.Status.objects.create(
            content="bleh", user=self.local_user, privacy="followers"
        )
        status.raise_visible_to_user(self.local_user)
        with self.assertRaises(Http404):
            status.raise_visible_to_user(self.remote_user)
        with self.assertRaises(Http404):
            status.raise_visible_to_user(self.anonymous_user)

        self.local_user.followers.add(self.remote_user)
        self.assertIsNone(status.raise_visible_to_user(self.remote_user))

    def test_raise_visible_to_user_followers_mentioned(self, *_):
        """privacy settings"""
        status = models.Status.objects.create(
            content="bleh", user=self.local_user, privacy="followers"
        )
        status.mention_users.set([self.remote_user])
        self.assertIsNone(status.raise_visible_to_user(self.remote_user))

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    def test_raise_visible_to_user_direct(self, *_):
        """privacy settings"""
        status = models.Status.objects.create(
            content="bleh", user=self.local_user, privacy="direct"
        )
        status.raise_visible_to_user(self.local_user)
        with self.assertRaises(Http404):
            status.raise_visible_to_user(self.remote_user)
        with self.assertRaises(Http404):
            status.raise_visible_to_user(self.anonymous_user)

        # mentioned user
        status.mention_users.set([self.remote_user])
        self.assertIsNone(status.raise_visible_to_user(self.remote_user))
