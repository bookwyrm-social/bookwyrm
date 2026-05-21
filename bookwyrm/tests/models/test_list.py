"""testing models"""

from uuid import UUID
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from bookwyrm import activitypub
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
            cls.another_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )
            cls.instance_user = activitypub.get_representative()
        cls.work = models.Work.objects.create(title="hello")
        cls.book = models.Edition.objects.create(title="hi", parent_work=cls.work)

    def test_remote_id(self, *_):
        """shelves use custom remote ids"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)
        expected_id = f"{settings.BASE_URL}/list/{book_list.id}"
        self.assertEqual(book_list.get_remote_id(), expected_id)

    def test_to_activity_list(self, *_):
        """jsonify it"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)
        activity_json = book_list.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], book_list.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "BookList")
        self.assertEqual(activity_json["name"], "Test List")
        self.assertEqual(activity_json["owner"], self.local_user.remote_id)

    def test_to_activity_suggestion_list(self, *_):
        """jsonify it"""
        book_list = models.SuggestionList.objects.create(suggests_for=self.work)
        activity_json = book_list.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], book_list.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "SuggestionList")
        self.assertEqual(activity_json["owner"], self.instance_user.remote_id)
        self.assertEqual(activity_json["book"]["id"], self.work.remote_id)

    def test_list_item(self, *_):
        """a list entry"""
        book_list = models.List.objects.create(
            name="Test List", user=self.local_user, privacy="unlisted"
        )

        item = models.ListItem.objects.create(
            book_list=book_list,
            edition=self.book,
            user=self.local_user,
            order=1,
        )

        self.assertTrue(item.approved)
        self.assertEqual(item.privacy, "unlisted")
        self.assertEqual(item.recipients, [])
        self.assertEqual(item.edition, self.book)
        self.assertEqual(item.order, 1)
        self.assertEqual(item.work, self.work)
        self.assertEqual(book_list.editions.first(), self.book)
        self.assertEqual(book_list.works.first(), self.book.parent_work)

    def test_suggestion_list_item(self, *_):
        """a suggestion list entry"""
        book_list = models.SuggestionList.objects.create(suggests_for=self.work)

        item = models.SuggestionListItem.objects.create(
            book_list=book_list,
            work=self.work,
            user=self.local_user,
        )

        self.assertEqual(item.privacy, "public")
        self.assertEqual(item.edition, self.book)
        self.assertEqual(item.work, self.work)
        self.assertEqual(book_list.editions.first(), self.book)
        self.assertEqual(book_list.works.first(), self.book.parent_work)

    def test_list_item_pending(self, *_):
        """a list entry"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)

        item = models.ListItem.objects.create(
            book_list=book_list,
            edition=self.book,
            user=self.local_user,
            approved=False,
            order=1,
        )

        self.assertFalse(item.approved)
        self.assertEqual(item.book_list.privacy, "public")
        self.assertEqual(item.privacy, "direct")
        self.assertEqual(item.recipients, [])

    def test_raise_not_submittable(self, *_):
        """user trying to add to list they shouldn't access"""
        book_list = models.List.objects.create(
            name="Test List", user=self.local_user, privacy="public", curation="open"
        )
        result = book_list.raise_not_submittable(self.another_user)
        self.assertIsNone(result)

        book_list = models.List.objects.create(
            name="Test List", user=self.local_user, privacy="public", curation="curated"
        )
        result = book_list.raise_not_submittable(self.another_user)
        self.assertIsNone(result)

        book_list = models.List.objects.create(
            name="Test List", user=self.local_user, privacy="public", curation="closed"
        )
        with self.assertRaises(PermissionDenied):
            book_list.raise_not_submittable(self.another_user)

    def test_embed_key(self, *_):
        """embed_key should never be empty"""
        book_list = models.List.objects.create(name="Test List", user=self.local_user)

        self.assertIsInstance(book_list.embed_key, UUID)
