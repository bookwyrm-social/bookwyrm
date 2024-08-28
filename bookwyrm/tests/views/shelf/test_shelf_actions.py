""" test for app action functionality """
import json
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.remove_book_statuses_task.delay")
class ShelfActionViews(TestCase):
    """tag views"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
            cls.another_user = models.User.objects.create_user(
                "rat@local.com",
                "rat@rat.com",
                "ratword",
                local=True,
                localname="rat",
                remote_id="https://example.com/users/rat",
            )
        cls.work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            cls.shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=cls.local_user
            )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_shelve(self, *_):
        """shelve a book"""
        request = self.factory.post(
            "", {"book": self.book.id, "shelf": self.shelf.identifier}
        )
        request.user = self.local_user
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            views.shelve(request)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Add")

        item = models.ShelfBook.objects.get()
        self.assertEqual(activity["object"]["id"], item.remote_id)
        # make sure the book is on the shelf
        self.assertEqual(self.shelf.books.get(), self.book)

    def test_shelve_to_read(self, *_):
        """special behavior for the to-read shelf"""
        shelf = models.Shelf.objects.get(user=self.local_user, identifier="to-read")
        request = self.factory.post(
            "", {"book": self.book.id, "shelf": shelf.identifier}
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.shelve(request)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

    def test_shelve_reading(self, *_):
        """special behavior for the reading shelf"""
        shelf = models.Shelf.objects.get(user=self.local_user, identifier="reading")
        request = self.factory.post(
            "", {"book": self.book.id, "shelf": shelf.identifier}
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.shelve(request)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

    def test_shelve_read(self, *_):
        """special behavior for the read shelf"""
        shelf = models.Shelf.objects.get(user=self.local_user, identifier="read")
        request = self.factory.post(
            "", {"book": self.book.id, "shelf": shelf.identifier}
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.shelve(request)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)

    def test_shelve_read_with_change_shelf(self, *_):
        """special behavior for the read shelf"""
        previous_shelf = models.Shelf.objects.get(
            user=self.local_user, identifier="reading"
        )
        models.ShelfBook.objects.create(
            shelf=previous_shelf, user=self.local_user, book=self.book
        )
        shelf = models.Shelf.objects.get(user=self.local_user, identifier="read")

        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "shelf": shelf.identifier,
                "change-shelf-from": previous_shelf.identifier,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.shelve(request)
        # make sure the book is on the shelf
        self.assertEqual(shelf.books.get(), self.book)
        self.assertEqual(list(previous_shelf.books.all()), [])

    def test_unshelve(self, *_):
        """remove a book from a shelf"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ShelfBook.objects.create(
                book=self.book, user=self.local_user, shelf=self.shelf
            )
        item = models.ShelfBook.objects.get()

        self.shelf.save()
        self.assertEqual(self.shelf.books.count(), 1)
        request = self.factory.post("", {"book": self.book.id, "shelf": self.shelf.id})
        request.user = self.local_user
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            views.unshelve(request)
        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Remove")
        self.assertEqual(activity["object"]["id"], item.remote_id)
        self.assertEqual(self.shelf.books.count(), 0)

    def test_create_shelf(self, *_):
        """a brand new custom shelf"""
        form = forms.ShelfForm()
        form.data["user"] = self.local_user.id
        form.data["name"] = "new shelf name"
        form.data["description"] = "desc"
        form.data["privacy"] = "unlisted"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        views.create_shelf(request)

        shelf = models.Shelf.objects.get(user=self.local_user, name="new shelf name")
        self.assertEqual(shelf.privacy, "unlisted")
        self.assertEqual(shelf.description, "desc")
        self.assertEqual(shelf.user, self.local_user)

    def test_create_shelf_wrong_user(self, *_):
        """a brand new custom shelf"""
        form = forms.ShelfForm()
        form.data["user"] = self.another_user.id
        form.data["name"] = "new shelf name"
        form.data["description"] = "desc"
        form.data["privacy"] = "unlisted"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with self.assertRaises(PermissionDenied):
            views.create_shelf(request)

    def test_delete_shelf(self, *_):
        """delete a brand new custom shelf"""
        request = self.factory.post("")
        request.user = self.local_user
        shelf_id = self.shelf.id

        views.delete_shelf(request, shelf_id)

        self.assertFalse(models.Shelf.objects.filter(id=shelf_id).exists())

    def test_delete_shelf_unauthorized(self, *_):
        """delete a brand new custom shelf"""
        request = self.factory.post("")
        request.user = self.another_user

        with self.assertRaises(PermissionDenied):
            views.delete_shelf(request, self.shelf.id)

        self.assertTrue(models.Shelf.objects.filter(id=self.shelf.id).exists())

    def test_delete_shelf_has_book(self, *_):
        """delete a brand new custom shelf"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ShelfBook.objects.create(
                book=self.book, user=self.local_user, shelf=self.shelf
            )
        request = self.factory.post("")
        request.user = self.local_user

        with self.assertRaises(PermissionDenied):
            views.delete_shelf(request, self.shelf.id)

        self.assertTrue(models.Shelf.objects.filter(id=self.shelf.id).exists())

    def test_delete_shelf_not_editable(self, *_):
        """delete a brand new custom shelf"""
        shelf = self.local_user.shelf_set.first()
        self.assertFalse(shelf.editable)
        request = self.factory.post("")
        request.user = self.local_user

        with self.assertRaises(PermissionDenied):
            views.delete_shelf(request, shelf.id)

        self.assertTrue(models.Shelf.objects.filter(id=shelf.id).exists())
