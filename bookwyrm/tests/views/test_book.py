""" test for app action functionality """
from io import BytesIO
import pathlib
from unittest.mock import patch

from PIL import Image
import responses

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse


class BookViews(TestCase):
    """books books books"""

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
        self.group = Group.objects.create(name="editor")
        self.group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        models.SiteSettings.objects.create()

    def test_book_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Book.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.books.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.book.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_edit_book_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditBook.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_edit_book(self):
        """lets a user edit a book"""
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.book.id)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")

    def test_edit_book_add_author(self):
        """lets a user edit a book with new authors"""
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["add_author"] = "Sappho"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request, self.book.id)
        result.render()

        # the changes haven't been saved yet
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Example Edition")

    def test_edit_book_add_new_author_confirm(self):
        """lets a user edit a book confirmed with new authors"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["author-match-count"] = 1
        form.data["author_match-0"] = "Sappho"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.book.id)

        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")
        self.assertEqual(self.book.authors.first().name, "Sappho")

    def test_edit_book_remove_author(self):
        """remove an author from a book"""
        author = models.Author.objects.create(name="Sappho")
        self.book.authors.add(author)
        form = forms.EditionForm(instance=self.book)
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["remove_authors"] = [author.id]
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.book.id)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")
        self.assertFalse(self.book.authors.exists())

    def test_create_book(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)
        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work.title, "New Title")

    def test_create_book_existing_work(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["parent_work"] = self.work.id
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)
        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work, self.work)

    def test_create_book_with_author(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["author-match-count"] = "1"
        form.data["author_match-0"] = "Sappho"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)
        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work.title, "New Title")
        self.assertEqual(book.authors.first().name, "Sappho")
        self.assertEqual(book.authors.first(), book.parent_work.authors.first())

    def test_switch_edition(self):
        """updates user's relationships to a book"""
        work = models.Work.objects.create(title="test work")
        edition1 = models.Edition.objects.create(title="first ed", parent_work=work)
        edition2 = models.Edition.objects.create(title="second ed", parent_work=work)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = models.Shelf.objects.create(name="Test Shelf", user=self.local_user)
            models.ShelfBook.objects.create(
                book=edition1,
                user=self.local_user,
                shelf=shelf,
            )
        models.ReadThrough.objects.create(user=self.local_user, book=edition1)

        self.assertEqual(models.ShelfBook.objects.get().book, edition1)
        self.assertEqual(models.ReadThrough.objects.get().book, edition1)
        request = self.factory.post("", {"edition": edition2.id})
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.switch_edition(request)

        self.assertEqual(models.ShelfBook.objects.get().book, edition2)
        self.assertEqual(models.ReadThrough.objects.get().book, edition2)

    def test_editions_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Editions.as_view()
        request = self.factory.get("")
        with patch("bookwyrm.views.books.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("")
        with patch("bookwyrm.views.books.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.work.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_upload_cover_file(self):
        """add a cover via file upload"""
        self.assertFalse(self.book.cover)
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )

        form = forms.CoverForm(instance=self.book)
        form.data["cover"] = SimpleUploadedFile(
            image_file, open(image_file, "rb").read(), content_type="image/jpeg"
        )

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            views.upload_cover(request, self.book.id)
            self.assertEqual(delay_mock.call_count, 1)

        self.book.refresh_from_db()
        self.assertTrue(self.book.cover)

    @responses.activate
    def test_upload_cover_url(self):
        """add a cover via url"""
        self.assertFalse(self.book.cover)
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)
        responses.add(
            responses.GET,
            "http://example.com",
            body=output.getvalue(),
            status=200,
        )

        form = forms.CoverForm(instance=self.book)
        form.data["cover-url"] = "http://example.com"

        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            views.upload_cover(request, self.book.id)
            self.assertEqual(delay_mock.call_count, 1)

        self.book.refresh_from_db()
        self.assertTrue(self.book.cover)
