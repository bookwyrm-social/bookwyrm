""" test for app action functionality """
import pathlib
from unittest.mock import patch

import responses

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse
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

    def test_book_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Book.as_view()
        models.ReadThrough.objects.create(
            user=self.local_user,
            book=self.book,
            start_date=timezone.now(),
        )
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.book.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_book_page_statuses(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Book.as_view()

        review = models.Review.objects.create(
            user=self.local_user,
            book=self.book,
            content="hi",
        )

        comment = models.Comment.objects.create(
            user=self.local_user,
            book=self.book,
            content="hi",
        )

        quote = models.Quotation.objects.create(
            user=self.local_user,
            book=self.book,
            content="hi",
            quote="wow",
        )

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id, user_statuses="review")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["statuses"].object_list[0], review)

        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id, user_statuses="comment")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["statuses"].object_list[0], comment)

        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id, user_statuses="quotation")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["statuses"].object_list[0], quote)

    def test_book_page_invalid_id(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Book.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, 0)

    def test_book_page_work_id(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Book.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["book"], self.book)

    def test_upload_cover_file(self):
        """add a cover via file upload"""
        self.assertFalse(self.book.cover)
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../../static/images/default_avi.jpg"
        )

        form = forms.CoverForm(instance=self.book)
        with open(image_path, "rb") as image_file:
            form.data["cover"] = SimpleUploadedFile(
                image_path, image_file.read(), content_type="image/jpeg"
            )

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            views.upload_cover(request, self.book.id)
            self.assertEqual(delay_mock.call_count, 1)

        self.book.refresh_from_db()
        self.assertTrue(self.book.cover)

    @responses.activate
    def test_upload_cover_url(self):
        """add a cover via url"""
        self.assertFalse(self.book.cover)
        form = forms.CoverForm(instance=self.book)
        form.data["cover-url"] = _setup_cover_url()

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            views.upload_cover(request, self.book.id)
            self.assertEqual(delay_mock.call_count, 1)

        self.book.refresh_from_db()
        self.assertTrue(self.book.cover)

    def test_add_description(self):
        """add a book description"""
        self.local_user.groups.add(self.group)
        request = self.factory.post("", {"description": "new description hi"})
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.add_description(request, self.book.id)

        self.book.refresh_from_db()
        self.assertEqual(self.book.description, "new description hi")
        self.assertEqual(self.book.last_edited_by, self.local_user)

    def test_update_book_from_remote(self):
        """call out to sync with remote connector"""
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

        with patch(
            "bookwyrm.connectors.openlibrary.Connector.update_book_from_remote"
        ) as mock:
            views.update_book_from_remote(request, self.book.id, "openlibrary.org")
        self.assertEqual(mock.call_count, 1)

    def test_resolve_book(self):
        """load a book from search results"""
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
        request = self.factory.post(
            "", {"remote_id": "https://openlibrary.org/book/123"}
        )
        request.user = self.local_user

        with patch(
            "bookwyrm.connectors.openlibrary.Connector.get_or_create_book"
        ) as mock:
            mock.return_value = self.book
            result = views.resolve_book(request)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args[0][0], "https://openlibrary.org/book/123")
        self.assertEqual(result.status_code, 302)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_quotation_endposition(self, *_):
        """make sure the endposition is served as well"""
        view = views.Book.as_view()

        _ = models.Quotation.objects.create(
            user=self.local_user,
            book=self.book,
            content="hi",
            quote="wow",
            position="12",
            endposition="13",
        )

        request = self.factory.get("")
        request.user = self.local_user

        with patch("bookwyrm.views.books.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id, user_statuses="quotation")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        print(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.context_data["statuses"].object_list[0].endposition, "13"
        )


def _setup_cover_url():
    """creates cover url mock"""
    cover_url = "http://example.com"
    image_path = pathlib.Path(__file__).parent.joinpath(
        "../../../static/images/default_avi.jpg"
    )
    with open(image_path, "rb") as image_file:
        responses.add(
            responses.GET,
            cover_url,
            body=image_file.read(),
            status=200,
        )
    return cover_url
