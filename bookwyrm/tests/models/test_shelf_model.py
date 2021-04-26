""" testing models """
import json
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, settings


# pylint: disable=unused-argument
class Shelf(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """look, a shelf"""
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_remote_id(self):
        """shelves use custom remote ids"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        expected_id = "https://%s/user/mouse/books/test-shelf" % settings.DOMAIN
        self.assertEqual(shelf.get_remote_id(), expected_id)

    def test_to_activity(self):
        """jsonify it"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
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

    def test_create_update_shelf(self):
        """create and broadcast shelf creation"""

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Create")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["name"], "Test Shelf")

        shelf.name = "arthur russel"
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            shelf.save()
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["name"], "arthur russel")
        self.assertEqual(shelf.name, "arthur russel")

    def test_shelve(self):
        """create and broadcast shelf creation"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            shelf_book = models.ShelfBook.objects.create(
                shelf=shelf, user=self.local_user, book=self.book
            )
        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Add")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], shelf_book.remote_id)
        self.assertEqual(activity["target"], shelf.remote_id)
        self.assertEqual(shelf.books.first(), self.book)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            shelf_book.delete()
        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Remove")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], shelf_book.remote_id)
        self.assertEqual(activity["target"], shelf.remote_id)
        self.assertFalse(shelf.books.exists())
