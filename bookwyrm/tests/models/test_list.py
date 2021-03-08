""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, settings


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class List(TestCase):
    """ some activitypub oddness ahead """

    def setUp(self):
        """ look, a list """
        self.user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.list = models.List.objects.create(name="Test List", user=self.user)

    def test_remote_id(self, _):
        """ shelves use custom remote ids """
        expected_id = "https://%s/list/%d" % (settings.DOMAIN, self.list.id)
        self.assertEqual(self.list.get_remote_id(), expected_id)

    def test_to_activity(self, _):
        """ jsonify it """
        activity_json = self.list.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json["id"], self.list.remote_id)
        self.assertEqual(activity_json["totalItems"], 0)
        self.assertEqual(activity_json["type"], "BookList")
        self.assertEqual(activity_json["name"], "Test List")
        self.assertEqual(activity_json["owner"], self.user.remote_id)

    def test_list_item(self, _):
        """ a list entry """
        work = models.Work.objects.create(title="hello")
        book = models.Edition.objects.create(title="hi", parent_work=work)
        item = models.ListItem.objects.create(
            book_list=self.list,
            book=book,
            user=self.user,
        )

        self.assertTrue(item.approved)

        add_activity = item.to_add_activity()
        self.assertEqual(add_activity["actor"], self.user.remote_id)
        self.assertEqual(add_activity["object"]["id"], book.remote_id)
        self.assertEqual(add_activity["target"], self.list.remote_id)

        remove_activity = item.to_remove_activity()
        self.assertEqual(remove_activity["actor"], self.user.remote_id)
        self.assertEqual(remove_activity["object"]["id"], book.remote_id)
        self.assertEqual(remove_activity["target"], self.list.remote_id)
