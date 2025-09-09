""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.query_logger import QueryLogger, raise_long_query_runtime
from bookwyrm.tests.validate_html import validate_html


# pylint: disable=invalid-name
class AuthorViews(TestCase):
    """author views"""

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
        cls.group = Group.objects.create(name="editor")
        cls.group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )
        cls.work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_author_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        author = models.Author.objects.create(name="Jessica")
        self.book.authors.add(author)
        request = self.factory.get("")
        request.user = self.local_user
        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.views.author.is_api_request") as is_api:
                is_api.return_value = False
                result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_author_page_edition_author(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
            isbn_13="9780300112511",
        )
        author = models.Author.objects.create(name="Jessica")
        self.book.authors.add(author)
        request = self.factory.get("")
        request.user = self.local_user
        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.views.author.is_api_request") as is_api:
                is_api.return_value = False
                result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        books = result.context_data["books"]
        self.assertEqual(books.object_list.count(), 1)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_author_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        author = models.Author.objects.create(name="Jessica")
        request = self.factory.get("")
        request.user = self.local_user
        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.views.author.is_api_request") as is_api:
                is_api.return_value = False
                result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_author_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        author = models.Author.objects.create(name="Jessica")
        request = self.factory.get("")
        request.user = self.anonymous_user
        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.views.author.is_api_request") as is_api:
                is_api.return_value = False
                result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_author_page_api_response(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        author = models.Author.objects.create(name="Jessica")
        request = self.factory.get("")
        request.user = self.local_user
        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.views.author.is_api_request") as is_api:
                is_api.return_value = True
                result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_edit_author_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditAuthor.as_view()
        author = models.Author.objects.create(name="Test Author")
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            result = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_edit_author(self):
        """edit an author"""
        view = views.EditAuthor.as_view()
        author = models.Author.objects.create(name="Test Author")
        self.local_user.groups.add(self.group)
        form = forms.AuthorForm(instance=author)
        form.data["name"] = "New Name"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
                view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        author.refresh_from_db()
        self.assertEqual(author.name, "New Name")
        self.assertEqual(author.last_edited_by, self.local_user)

    def test_edit_author_non_editor(self):
        """edit an author with invalid post data"""
        view = views.EditAuthor.as_view()
        author = models.Author.objects.create(name="Test Author")
        form = forms.AuthorForm(instance=author)
        form.data["name"] = "New Name"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with self.assertRaises(PermissionDenied):
                view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        author.refresh_from_db()
        self.assertEqual(author.name, "Test Author")

    def test_edit_author_invalid_form(self):
        """edit an author with invalid post data"""
        view = views.EditAuthor.as_view()
        author = models.Author.objects.create(name="Test Author")
        self.local_user.groups.add(self.group)
        form = forms.AuthorForm(instance=author)
        form.data["name"] = ""
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            resp = view(request, author.id)
            raise_long_query_runtime(query_logger.queries)
        author.refresh_from_db()
        self.assertEqual(author.name, "Test Author")
        validate_html(resp.render())
        self.assertEqual(resp.status_code, 200)

    def test_update_author_from_remote(self):
        """call out to sync with remote connector"""
        author = models.Author.objects.create(name="Test Author")
        models.Connector.objects.create(
            identifier="openlibrary.org",
            name="OpenLibrary",
            connector_file="openlibrary",
            base_url="https://openlibrary.org",
            books_url="https://openlibrary.org",
            covers_url="https://covers.openlibrary.org",
            search_url="https://openlibrary.org/search?q=",
            isbn_search_url="https://openlibrary.org/isbn",
        )
        self.local_user.groups.add(self.group)
        request = self.factory.post("")
        request.user = self.local_user

        query_logger = QueryLogger()
        with connection.execute_wrapper(query_logger):
            with patch(
                "bookwyrm.connectors.openlibrary.Connector.update_author_from_remote"
            ) as mock:
                views.update_author_from_remote(request, author.id, "openlibrary.org")
            self.assertEqual(mock.call_count, 1)
            raise_long_query_runtime(query_logger.queries)
