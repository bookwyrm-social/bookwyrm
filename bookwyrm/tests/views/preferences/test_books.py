"""test for app action functionality"""

from unittest.mock import patch

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class BlockedBooksViews(TestCase):
    """block and unblock books"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""

        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )

        cls.work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_block_get(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.BlockedBooks.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_block_book(self, _):
        """block a book"""

        self.assertFalse(self.work in self.local_user.blocked_books.all())

        view = views.BlockedBooks.as_view()
        request = self.factory.post("")
        request.user = self.local_user

        view(request, self.book.id)

        self.assertTrue(self.work in self.local_user.blocked_books.all())

    def test_unblock_book(self, _):
        """undo a block"""

        self.local_user.blocked_books.add(self.work)
        self.assertTrue(self.work in self.local_user.blocked_books.all())

        request = self.factory.post("")
        request.user = self.local_user
        views.unblock_book(request, self.book.id)

        self.assertFalse(self.work in self.local_user.blocked_books.all())
