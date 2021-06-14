""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, settings


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class List(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """look, a list"""
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        work = models.Work.objects.create(title="hello")
        self.book = models.Edition.objects.create(title="hi", parent_work=work)

    def test_remote_id(self, _):
        """shelves use custom remote ids"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            book_list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        expected_id = "https://%s/list/%d" % (settings.DOMAIN, book_list.id)
        self.assertEqual(book_list.get_remote_id(), expected_id)

    def test_to_activity(self, _):
        """jsonify it"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            book_list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        activity_json = book_list.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], book_list.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "BookList")
        self.assertEqual(activity_json["name"], "Test List")
        self.assertEqual(activity_json["owner"], self.local_user.remote_id)

    def test_list_item(self, _):
        """a list entry"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
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

    def test_list_item_pending(self, _):
        """a list entry"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            book_list = models.List.objects.create(
                name="Test List", user=self.local_user
            )

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
