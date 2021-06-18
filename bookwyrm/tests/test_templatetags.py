""" style fixes and lookups for templates """
import re
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.templatetags import (
    bookwyrm_tags,
    interaction,
    markdown,
    status_display,
    utilities,
)


@patch("bookwyrm.activitystreams.ActivityStream.add_status")
@patch("bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores")
class TemplateTags(TestCase):
    """lotta different things here"""

    def setUp(self):
        """create some filler objects"""
        self.user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.mouse",
            "mouseword",
            local=True,
            localname="mouse",
        )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.rat",
                "ratword",
                remote_id="http://example.com/rat",
                local=False,
            )
        self.book = models.Edition.objects.create(title="Test Book")

    def test_get_user_rating(self, *_):
        """get a user's most recent rating of a book"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.Review.objects.create(user=self.user, book=self.book, rating=3)
        self.assertEqual(bookwyrm_tags.get_user_rating(self.book, self.user), 3)

    def test_get_user_rating_doesnt_exist(self, *_):
        """there is no rating available"""
        self.assertEqual(bookwyrm_tags.get_user_rating(self.book, self.user), 0)

    def test_get_user_identifer_local(self, *_):
        """fall back to the simplest uid available"""
        self.assertNotEqual(self.user.username, self.user.localname)
        self.assertEqual(utilities.get_user_identifier(self.user), "mouse")

    def test_get_user_identifer_remote(self, *_):
        """for a remote user, should be their full username"""
        self.assertEqual(
            utilities.get_user_identifier(self.remote_user), "rat@example.com"
        )

    def test_get_replies(self, *_):
        """direct replies to a status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            parent = models.Review.objects.create(
                user=self.user, book=self.book, content="hi"
            )
            first_child = models.Status.objects.create(
                reply_parent=parent, user=self.user, content="hi"
            )
            second_child = models.Status.objects.create(
                reply_parent=parent, user=self.user, content="hi"
            )
            with patch(
                "bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores"
            ):
                third_child = models.Status.objects.create(
                    reply_parent=parent,
                    user=self.user,
                    deleted=True,
                    deleted_date=timezone.now(),
                )

        replies = status_display.get_replies(parent)
        self.assertEqual(len(replies), 2)
        self.assertTrue(first_child in replies)
        self.assertTrue(second_child in replies)
        self.assertFalse(third_child in replies)

    def test_get_parent(self, *_):
        """get the reply parent of a status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            parent = models.Review.objects.create(
                user=self.user, book=self.book, content="hi"
            )
            child = models.Status.objects.create(
                reply_parent=parent, user=self.user, content="hi"
            )

        result = status_display.get_parent(child)
        self.assertEqual(result, parent)
        self.assertIsInstance(result, models.Review)

    def test_get_user_liked(self, *_):
        """did a user like a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_liked(self.user, status))
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.Favorite.objects.create(user=self.user, status=status)
        self.assertTrue(interaction.get_user_liked(self.user, status))

    def test_get_user_boosted(self, *_):
        """did a user boost a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_boosted(self.user, status))
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.Boost.objects.create(user=self.user, boosted_status=status)
        self.assertTrue(interaction.get_user_boosted(self.user, status))

    def test_get_boosted(self, *_):
        """load a boosted status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Review.objects.create(user=self.remote_user, book=self.book)
            boost = models.Boost.objects.create(user=self.user, boosted_status=status)
        boosted = status_display.get_boosted(boost)
        self.assertIsInstance(boosted, models.Review)
        self.assertEqual(boosted, status)

    def test_get_book_description(self, *_):
        """grab it from the edition or the parent"""
        work = models.Work.objects.create(title="Test Work")
        self.book.parent_work = work
        self.book.save()

        self.assertIsNone(bookwyrm_tags.get_book_description(self.book))

        work.description = "hi"
        work.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), "hi")

        self.book.description = "hello"
        self.book.save()
        self.assertEqual(bookwyrm_tags.get_book_description(self.book), "hello")

    def test_get_uuid(self, *_):
        """uuid functionality"""
        uuid = utilities.get_uuid("hi")
        self.assertTrue(re.match(r"hi[A-Za-z0-9\-]", uuid))

    def test_get_markdown(self, *_):
        """mardown format data"""
        result = markdown.get_markdown("_hi_")
        self.assertEqual(result, "<p><em>hi</em></p>")

        result = markdown.get_markdown("<marquee>_hi_</marquee>")
        self.assertEqual(result, "<p><em>hi</em></p>")

    def test_get_mentions(self, *_):
        """list of people mentioned"""
        status = models.Status.objects.create(content="hi", user=self.remote_user)
        result = status_display.get_mentions(status, self.user)
        self.assertEqual(result, "@rat@example.com ")

    def test_related_status(self, *_):
        """gets the subclass model for a notification status"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(content="hi", user=self.user)
        notification = models.Notification.objects.create(
            user=self.user, notification_type="MENTION", related_status=status
        )

        result = bookwyrm_tags.related_status(notification)
        self.assertIsInstance(result, models.Status)
