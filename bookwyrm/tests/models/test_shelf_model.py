""" testing models """
from django.test import TestCase

from bookwyrm import models, settings


# pylint: disable=unused-argument
class Shelf(TestCase):
    """ some activitypub oddness ahead """

    def setUp(self):
        """ look, a shelf """
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)

    def test_remote_id(self):
        """ shelves use custom remote ids """
        real_broadcast = models.Shelf.broadcast

        def broadcast_mock(_, activity, user, **kwargs):
            """ nah """

        models.Shelf.broadcast = broadcast_mock
        shelf = models.Shelf.objects.create(
            name="Test Shelf", identifier="test-shelf", user=self.local_user
        )
        expected_id = "https://%s/user/mouse/shelf/test-shelf" % settings.DOMAIN
        self.assertEqual(shelf.get_remote_id(), expected_id)
        models.Shelf.broadcast = real_broadcast

    def test_to_activity(self):
        """ jsonify it """
        real_broadcast = models.Shelf.broadcast

        def empty_mock(_, activity, user, **kwargs):
            """ nah """

        models.Shelf.broadcast = empty_mock
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
        models.Shelf.broadcast = real_broadcast

    def test_create_update_shelf(self):
        """ create and broadcast shelf creation """
        real_broadcast = models.Shelf.broadcast

        def create_mock(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Create")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["name"], "Test Shelf")

        models.Shelf.broadcast = create_mock

        shelf = models.Shelf.objects.create(
            name="Test Shelf", identifier="test-shelf", user=self.local_user
        )

        def update_mock(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Update")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["name"], "arthur russel")

        models.Shelf.broadcast = update_mock

        shelf.name = "arthur russel"
        shelf.save()
        self.assertEqual(shelf.name, "arthur russel")
        models.Shelf.broadcast = real_broadcast

    def test_shelve(self):
        """ create and broadcast shelf creation """
        real_broadcast = models.Shelf.broadcast
        real_shelfbook_broadcast = models.ShelfBook.broadcast

        def add_mock(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["id"], self.book.remote_id)
            self.assertEqual(activity["target"], shelf.remote_id)

        def remove_mock(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Remove")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["id"], self.book.remote_id)
            self.assertEqual(activity["target"], shelf.remote_id)

        def empty_mock(_, activity, user, **kwargs):
            """ nah """

        models.Shelf.broadcast = empty_mock
        shelf = models.Shelf.objects.create(
            name="Test Shelf", identifier="test-shelf", user=self.local_user
        )

        models.ShelfBook.broadcast = add_mock
        shelf_book = models.ShelfBook.objects.create(
            shelf=shelf, user=self.local_user, book=self.book
        )
        self.assertEqual(shelf.books.first(), self.book)

        models.ShelfBook.broadcast = remove_mock
        shelf_book.delete()
        self.assertFalse(shelf.books.exists())

        models.ShelfBook.broadcast = real_shelfbook_broadcast
        models.Shelf.broadcast = real_broadcast
