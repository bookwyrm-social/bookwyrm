""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse

# pylint: disable=unused-argument
class ListViews(TestCase):
    """ tag views"""

    def setUp(self):
        """ we need basic test data and mocks """
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
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.list = models.List.objects.create(
                name="Test List", user=self.local_user
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_lists_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Lists.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_lists_create(self):
        """ create list view """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Create")
            self.assertEqual(activity["actor"], self.local_user.remote_id)

        models.List.broadcast = mock_broadcast

        view = views.Lists.as_view()
        request = self.factory.post(
            "",
            {
                "name": "A list",
                "description": "wow",
                "privacy": "unlisted",
                "curation": "open",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user
        result = view(request)
        self.assertEqual(result.status_code, 302)
        new_list = models.List.objects.filter(name="A list").get()
        self.assertEqual(new_list.description, "wow")
        self.assertEqual(new_list.privacy, "unlisted")
        self.assertEqual(new_list.curation, "open")
        models.List.broadcast = real_broadcast

    def test_list_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.List.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("/?page=1")
        request.user = self.local_user
        with patch("bookwyrm.views.list.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_list_edit(self):
        """ edit a list """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Update")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["id"], self.list.remote_id)

        models.List.broadcast = mock_broadcast

        view = views.List.as_view()
        request = self.factory.post(
            "",
            {
                "name": "New Name",
                "description": "wow",
                "privacy": "direct",
                "curation": "curated",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user

        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)

        self.list.refresh_from_db()
        self.assertEqual(self.list.name, "New Name")
        self.assertEqual(self.list.description, "wow")
        self.assertEqual(self.list.privacy, "direct")
        self.assertEqual(self.list.curation, "curated")
        models.List.broadcast = real_broadcast

    def test_curate_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.List.objects.create(name="Public list", user=self.local_user)
            models.List.objects.create(
                name="Private list", privacy="direct", user=self.local_user
            )
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)

    def test_curate_approve(self):
        """ approve a pending item """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user, **kwargs):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        models.ListItem.broadcast = mock_broadcast

        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
            )

        request = self.factory.post(
            "",
            {
                "item": pending.id,
                "approved": "true",
            },
        )
        request.user = self.local_user

        view(request, self.list.id)
        pending.refresh_from_db()
        self.assertEqual(self.list.books.count(), 1)
        self.assertEqual(self.list.listitem_set.first(), pending)
        self.assertTrue(pending.approved)
        models.ListItem.broadcast = real_broadcast

    def test_curate_reject(self):
        """ approve a pending item """
        view = views.Curate.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            pending = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=False,
            )

        request = self.factory.post(
            "",
            {
                "item": pending.id,
                "approved": "false",
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.list.id)
        self.assertFalse(self.list.books.exists())
        self.assertFalse(models.ListItem.objects.exists())

    def test_add_book(self):
        """ put a book on a list """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        models.ListItem.broadcast = mock_broadcast
        request = self.factory.post(
            "",
            {
                "book": self.book.id,
                "list": self.list.id,
            },
        )
        request.user = self.local_user

        views.list.add_book(request)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.local_user)
        self.assertTrue(item.approved)
        models.ListItem.broadcast = real_broadcast

    def test_add_book_outsider(self):
        """ put a book on a list """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user):
            """ ok """
            self.assertEqual(user.remote_id, self.rat.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.rat.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        models.ListItem.broadcast = mock_broadcast
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

        views.list.add_book(request)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.rat)
        self.assertTrue(item.approved)
        models.ListItem.broadcast = real_broadcast

    def test_add_book_pending(self):
        """ put a book on a list awaiting approval """
        real_broadcast = models.List.broadcast

        def mock_broadcast(_, activity, user):
            """ ok """
            self.assertEqual(user.remote_id, self.rat.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.rat.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)
            self.assertEqual(activity["object"]["id"], self.book.remote_id)

        models.ListItem.broadcast = mock_broadcast
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

        views.list.add_book(request)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.rat)
        self.assertFalse(item.approved)
        models.ListItem.broadcast = real_broadcast

    def test_add_book_self_curated(self):
        """ put a book on a list automatically approved """
        real_broadcast = models.ListItem.broadcast

        def mock_broadcast(_, activity, user):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Add")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        models.ListItem.broadcast = mock_broadcast

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

        views.list.add_book(request)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.user, self.local_user)
        self.assertTrue(item.approved)
        models.ListItem.broadcast = real_broadcast

    def test_remove_book(self):
        """ take an item off a list """
        real_broadcast = models.ListItem.broadcast

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            item = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
            )
        self.assertTrue(self.list.listitem_set.exists())

        def mock_broadcast(_, activity, user):
            """ ok """
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Remove")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["target"], self.list.remote_id)

        models.ListItem.broadcast = mock_broadcast
        request = self.factory.post(
            "",
            {
                "item": item.id,
            },
        )
        request.user = self.local_user

        views.list.remove_book(request, self.list.id)

        self.assertFalse(self.list.listitem_set.exists())
        models.ListItem.broadcast = real_broadcast

    def test_remove_book_unauthorized(self):
        """ take an item off a list """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            item = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
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
