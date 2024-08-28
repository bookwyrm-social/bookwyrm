""" testing models """
from uuid import UUID
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, settings


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.lists_stream.remove_list_task.delay")
class List(TestCase):
    """some activitypub oddness ahead"""

    @classmethod
    def setUpTestData(cls):
        """look, a list"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
        work = models.Work.objects.create(title="hello")
        cls.book = models.Edition.objects.create(title="hi", parent_work=work)

    def test_remote_id(self, *_):
        """shelves use custom remote ids"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)
        expected_id = f"{settings.BASE_URL}/list/{book_list.id}"
        self.assertEqual(book_list.get_remote_id(), expected_id)

    def test_to_activity(self, *_):
        """jsonify it"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)
        activity_json = book_list.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], book_list.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "BookList")
        self.assertEqual(activity_json["name"], "Test List")
        self.assertEqual(activity_json["owner"], self.local_user.remote_id)

    def test_list_item(self, *_):
        """a list entry"""
        book_list = models.List.objects.create(
            name="Test List", user=self.local_user, privacy="unlisted"
        )

        item = models.ListItem.objects.create(
            book_list=book_list,
            book=self.book,
            user=self.local_user,
            order=1,
        )

        self.assertTrue(item.approved)
        self.assertEqual(item.privacy, "unlisted")
        self.assertEqual(item.recipients, [])

    def test_list_item_pending(self, *_):
        """a list entry"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)

        item = models.ListItem.objects.create(
            book_list=book_list,
            book=self.book,
            user=self.local_user,
            approved=False,
            order=1,
        )

        self.assertFalse(item.approved)
        self.assertEqual(item.book_list.privacy, "public")
        self.assertEqual(item.privacy, "direct")
        self.assertEqual(item.recipients, [])

    def test_embed_key(self, *_):
        """embed_key should never be empty"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)

        self.assertIsInstance(book_list.embed_key, UUID)
