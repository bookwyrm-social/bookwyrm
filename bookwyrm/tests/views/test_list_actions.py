""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views

# pylint: disable=unused-argument
class ListActionViews(TestCase):
    """tag views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
            remote_id="https://example.com/users/mouse",
        )
        self.rat = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
        )
        work = models.Work.objects.create(title="Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        work_two = models.Work.objects.create(title="Labori")
        self.book_two = models.Edition.objects.create(
            title="Example Edition 2",
            remote_id="https://example.com/book/2",
            parent_work=work_two,
        )
        work_three = models.Work.objects.create(title="Trabajar")
        self.book_three = models.Edition.objects.create(
            title="Example Edition 3",
            remote_id="https://example.com/book/3",
            parent_work=work_three,
        )
        work_four = models.Work.objects.create(title="Travailler")
        self.book_four = models.Edition.objects.create(
            title="Example Edition 4",
            remote_id="https://example.com/book/4",
            parent_work=work_four,
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_curate_approve(self):
        """approve a pending item"""
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
                order=1,
            )

        request = self.factory.post(
            "",
            {
                "item": pending.id,
                "approved": "true",
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            view(request, self.list.id)

        self.assertEqual(mock.call_count, 2)
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Add")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["target"], self.list.remote_id)

        pending.refresh_from_db()
        self.assertEqual(self.list.books.count(), 1)
        self.assertEqual(self.list.listitem_set.first(), pending)
        self.assertTrue(pending.approved)

    def test_curate_reject(self):
        """approve a pending item"""
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
                order=1,
            )

        request = self.factory.post(
            "",
            {
                "item": pending.id,
                "approved": "false",
            },
        )
        request.user = self.local_user

        view(request, self.list.id)

        self.assertFalse(self.list.books.exists())
        self.assertFalse(models.ListItem.objects.exists())

    def test_add_book(self):
        """put a book on a list"""
        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.list.add_book(request)
            self.assertEqual(mock.call_count, 1)
            activity = json.loads(mock.call_args[0][1])
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.local_user)
        self.assertTrue(item.approved)

    def test_add_two_books(self):
        """
        Putting two books on the list. The first should have an order value of
        1 and the second should have an order value of 2.
        """
        request_one = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request_one.user = self.local_user

        request_two = self.factory.post(
            "",
            {
                "book": self.book_two.id,
                "list": self.list.id,
            },
        )
        request_two.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.add_book(request_one)
            views.list.add_book(request_two)

        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[1].book, self.book_two)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[1].order, 2)

    def test_add_three_books_and_remove_second(self):
        """
        Put three books on a list and then remove the one in the middle. The
        ordering of the list should adjust to not have a gap.
        """
        request_one = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request_one.user = self.local_user

        request_two = self.factory.post(
            "",
            {
                "book": self.book_two.id,
                "list": self.list.id,
            },
        )
        request_two.user = self.local_user

        request_three = self.factory.post(
            "",
            {
                "book": self.book_three.id,
                "list": self.list.id,
            },
        )
        request_three.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.add_book(request_one)
            views.list.add_book(request_two)
            views.list.add_book(request_three)

        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[1].book, self.book_two)
        self.assertEqual(items[2].book, self.book_three)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[1].order, 2)
        self.assertEqual(items[2].order, 3)

        remove_request = self.factory.post("", {"item": items[1].id})
        remove_request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.remove_book(remove_request, self.list.id)
        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[1].book, self.book_three)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[1].order, 2)

    def test_adding_book_with_a_pending_book(self):
        """
        When a list contains any pending books, the pending books should have
        be at the end of the list by order. If a book is added while a book is
        pending, its order should precede the pending books.
        """
        request = self.factory.post(
            "",
            {
                "book": self.book_three.id,
                "list": self.list.id,
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.rat,
                book=self.book_two,
                approved=False,
                order=2,
            )
            views.list.add_book(request)

        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[0].order, 1)
        self.assertTrue(items[0].approved)

        self.assertEqual(items[1].book, self.book_three)
        self.assertEqual(items[1].order, 2)
        self.assertTrue(items[1].approved)

        self.assertEqual(items[2].book, self.book_two)
        self.assertEqual(items[2].order, 3)
        self.assertFalse(items[2].approved)

    def test_approving_one_pending_book_from_multiple(self):
        """
        When a list contains any pending books, the pending books should have
        be at the end of the list by order. If a pending book is approved, then
        its order should be at the end of the approved books and before the
        remaining pending books.
        """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book_two,
                approved=True,
                order=2,
            )
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.rat,
                book=self.book_three,
                approved=False,
                order=3,
            )
            to_be_approved = models.ListItem.objects.create(
                book_list=self.list,
                user=self.rat,
                book=self.book_four,
                approved=False,
                order=4,
            )

        view = views.Curate.as_view()
        request = self.factory.post(
            "",
            {
                "item": to_be_approved.id,
                "approved": "true",
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.list.id)

        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[0].order, 1)
        self.assertTrue(items[0].approved)

        self.assertEqual(items[1].book, self.book_two)
        self.assertEqual(items[1].order, 2)
        self.assertTrue(items[1].approved)

        self.assertEqual(items[2].book, self.book_four)
        self.assertEqual(items[2].order, 3)
        self.assertTrue(items[2].approved)

        self.assertEqual(items[3].book, self.book_three)
        self.assertEqual(items[3].order, 4)
        self.assertFalse(items[3].approved)

    def test_add_three_books_and_move_last_to_first(self):
        """
        Put three books on the list and move the last book to the first
        position.
        """
        request_one = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request_one.user = self.local_user

        request_two = self.factory.post(
            "",
            {
                "book": self.book_two.id,
                "list": self.list.id,
            },
        )
        request_two.user = self.local_user

        request_three = self.factory.post(
            "",
            {
                "book": self.book_three.id,
                "list": self.list.id,
            },
        )
        request_three.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.add_book(request_one)
            views.list.add_book(request_two)
            views.list.add_book(request_three)

        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book)
        self.assertEqual(items[1].book, self.book_two)
        self.assertEqual(items[2].book, self.book_three)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[1].order, 2)
        self.assertEqual(items[2].order, 3)

        set_position_request = self.factory.post("", {"position": 1})
        set_position_request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.set_book_position(set_position_request, items[2].id)
        items = self.list.listitem_set.order_by("order").all()
        self.assertEqual(items[0].book, self.book_three)
        self.assertEqual(items[1].book, self.book)
        self.assertEqual(items[2].book, self.book_two)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[1].order, 2)
        self.assertEqual(items[2].order, 3)

    def test_add_book_outsider(self):
        """put a book on a list"""
        self.list.curation = "open"
        self.list.save(broadcast=False)
        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request.user = self.rat

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.list.add_book(request)
            self.assertEqual(mock.call_count, 1)
            activity = json.loads(mock.call_args[0][1])
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.rat.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.rat)
        self.assertTrue(item.approved)

    def test_add_book_pending(self):
        """put a book on a list awaiting approval"""
        self.list.curation = "curated"
        self.list.save(broadcast=False)
        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request.user = self.rat

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.list.add_book(request)

        self.assertEqual(mock.call_count, 1)
        activity = json.loads(mock.call_args[0][1])

        self.assertEqual(activity["type"], "Add")
        self.assertEqual(activity["actor"], self.rat.remote_id)
        self.assertEqual(activity["target"], self.list.remote_id)

        item = self.list.listitem_set.get()
        self.assertEqual(activity["object"]["id"], item.remote_id)

        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.rat)
        self.assertFalse(item.approved)

    def test_add_book_self_curated(self):
        """put a book on a list automatically approved"""
        self.list.curation = "curated"
        self.list.save(broadcast=False)
        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.list.add_book(request)
            self.assertEqual(mock.call_count, 1)
            activity = json.loads(mock.call_args[0][1])
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.local_user)
        self.assertTrue(item.approved)

    def test_remove_book(self):
        """take an item off a list"""

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            item = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                order=1,
            )
        self.assertTrue(self.list.listitem_set.exists())

        request = self.factory.post(
            "",
            {
                "item": item.id,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.list.remove_book(request, self.list.id)
        self.assertFalse(self.list.listitem_set.exists())

    def test_remove_book_unauthorized(self):
        """take an item off a list"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            item = models.ListItem.objects.create(
                book_list=self.list, user=self.local_user, book=self.book, order=1
            )
        self.assertTrue(self.list.listitem_set.exists())
        request = self.factory.post(
            "",
            {
                "item": item.id,
            },
        )
        request.user = self.rat

        views.list.remove_book(request, self.list.id)
        self.assertTrue(self.list.listitem_set.exists())
