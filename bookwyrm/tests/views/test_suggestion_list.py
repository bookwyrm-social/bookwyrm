""" test for app action functionality """
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse, get_representative
from bookwyrm.tests.validate_html import validate_html


class BookViews(TestCase):
    """books books books"""

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
        cls.another_book = models.Edition.objects.create(
            title="Another Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=models.Work.objects.create(title="Another Work"),
        )

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_suggestion_list_get(self, *_):
        """start a suggestion list for a book"""
        models.SuggestionList.objects.create(suggests_for=self.work)
        view = views.SuggestionList.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.book.id)
        validate_html(result.render())

    def test_suggestion_list_get_json(self, *_):
        """start a suggestion list for a book"""
        models.SuggestionList.objects.create(suggests_for=self.work)
        view = views.SuggestionList.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.views.suggestion_list.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.book.id)
        self.assertIsInstance(result, ActivitypubResponse)

    def test_suggestion_create(self, *_):
        """start a suggestion list for a book"""
        self.assertFalse(hasattr(self.work, "suggestion_list"))

        view = views.SuggestionList.as_view()
        form = forms.SuggestionListForm()
        form.data["suggests_for"] = self.work.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, self.book.id)

        self.work.refresh_from_db()
        self.assertTrue(hasattr(self.work, "suggestion_list"))

        suggestion_list = self.work.suggestion_list
        self.assertEqual(suggestion_list.suggests_for, self.work)
        self.assertEqual(suggestion_list.privacy, "public")
        self.assertEqual(suggestion_list.user, get_representative())

    def test_book_add_suggestion(self, *_):
        """Add a book to the recommendation list"""
        suggestion_list = models.SuggestionList.objects.create(suggests_for=self.work)
        view = views.book_add_suggestion

        form = forms.SuggestionListItemForm()
        form.data["user"] = self.local_user.id
        form.data["book"] = self.another_book.id
        form.data["book_list"] = suggestion_list.id
        form.data["notes"] = "hello"

        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request, self.work.id)

        self.assertEqual(suggestion_list.suggestionlistitem_set.count(), 1)
        item = suggestion_list.suggestionlistitem_set.first()
        self.assertEqual(item.book, self.another_book)
        self.assertEqual(item.user, self.local_user)
        self.assertEqual(item.notes, "hello")

    def test_book_remove_suggestion(self, *_):
        """Remove a book from the recommendation list"""
        suggestion_list = models.SuggestionList.objects.create(suggests_for=self.work)
        item = models.SuggestionListItem.objects.create(
            book_list=suggestion_list, user=self.local_user, book=self.another_book
        )
        self.assertEqual(suggestion_list.suggestionlistitem_set.count(), 1)

        view = views.book_remove_suggestion
        request = self.factory.post("", {"item": item.id})
        request.user = self.local_user

        view(request, self.work.id)

        self.assertEqual(suggestion_list.suggestionlistitem_set.count(), 0)

    def test_book_remove_suggestion_without_permission(self, *_):
        """Remove a book from the recommendation list"""
        suggestion_list = models.SuggestionList.objects.create(suggests_for=self.work)
        item = models.SuggestionListItem.objects.create(
            book_list=suggestion_list, user=self.local_user, book=self.another_book
        )
        self.assertEqual(suggestion_list.suggestionlistitem_set.count(), 1)

        view = views.book_remove_suggestion
        request = self.factory.post("", {"item": item.id})
        request.user = self.another_user

        with self.assertRaises(PermissionDenied):
            view(request, self.work.id)

        self.assertEqual(suggestion_list.suggestionlistitem_set.count(), 1)

    def test_endorse_suggestion(self, *_):
        """Endorse a suggestion"""
        suggestion_list = models.SuggestionList.objects.create(suggests_for=self.work)
        item = models.SuggestionListItem.objects.create(
            book_list=suggestion_list, user=self.local_user, book=self.another_book
        )
        self.assertEqual(item.endorsement.count(), 0)
        view = views.endorse_suggestion
        request = self.factory.post("")
        request.user = self.another_user

        view(request, self.work.id, item.id)

        self.assertEqual(item.endorsement.count(), 1)

    def test_endorse_suggestion_by_self(self, *_):
        """Endorse a suggestion error handling"""
        suggestion_list = models.SuggestionList.objects.create(suggests_for=self.work)
        item = models.SuggestionListItem.objects.create(
            book_list=suggestion_list, user=self.local_user, book=self.another_book
        )
        self.assertEqual(item.endorsement.count(), 0)
        view = views.endorse_suggestion
        request = self.factory.post("")
        request.user = self.local_user

        view(request, self.work.id, item.id)

        # no impact
        self.assertEqual(item.endorsement.count(), 0)
