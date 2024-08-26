""" test for app action functionality """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class ListItemViews(TestCase):
    """list view"""

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
        work = models.Work.objects.create(title="Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        with (
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
        ):
            cls.list = models.List.objects.create(name="Test List", user=cls.local_user)

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_add_list_item_notes(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ListItem.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            item = models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.book,
                approved=True,
                order=1,
            )
        request = self.factory.post(
            "",
            {
                "book_list": self.list.id,
                "book": self.book.id,
                "user": self.local_user.id,
                "notes": "beep boop",
            },
        )
        request.user = self.local_user
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            view(request, self.list.id, item.id)
        self.assertEqual(mock.call_count, 1)

        item.refresh_from_db()
        self.assertEqual(item.notes, "<p>beep boop</p>")
