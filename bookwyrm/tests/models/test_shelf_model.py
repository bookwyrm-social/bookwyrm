""" testing models """
import json
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, settings


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.remove_book_statuses_task.delay")
class Shelf(TestCase):
    """some activitypub oddness ahead"""

    @classmethod
    def setUpTestData(cls):
        """look, a shelf"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_remote_id(self, *_):
        """shelves use custom remote ids"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        expected_id = f"{settings.BASE_URL}/user/mouse/books/test-shelf"
        self.assertEqual(shelf.get_remote_id(), expected_id)

    def test_to_activity(self, *_):
        """jsonify it"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        activity_json = shelf.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], shelf.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "Shelf")
        self.assertEqual(activity_json["name"], "Test Shelf")
        self.assertEqual(activity_json["owner"], self.local_user.remote_id)

    def test_create_update_shelf(self, *_):
        """create and broadcast shelf creation"""

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Create")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["name"], "Test Shelf")

        shelf.name = "arthur russel"
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            shelf.save()
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["name"], "arthur russel")
        self.assertEqual(shelf.name, "arthur russel")

    def test_shelve(self, *_):
        """create and broadcast shelf creation"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            shelf_book = models.ShelfBook.objects.create(
                shelf=shelf, user=self.local_user, book=self.book
            )
        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Add")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], shelf_book.remote_id)
        self.assertEqual(activity["target"], shelf.remote_id)
        self.assertEqual(shelf.books.first(), self.book)

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            shelf_book.delete()
        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Remove")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], shelf_book.remote_id)
        self.assertEqual(activity["target"], shelf.remote_id)
        self.assertFalse(shelf.books.exists())
