""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse


class AuthorViews(TestCase):
    """author views"""

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

    def test_author_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Author.as_view()
        author = models.Author.objects.create(name="Jessica")
        request = self.factory.get("")
        with patch("bookwyrm.views.author.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, author.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("")
        with patch("bookwyrm.views.author.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, author.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_edit_author_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditAuthor.as_view()
        author = models.Author.objects.create(name="Test Author")
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, author.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
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

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, author.id)
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

        with self.assertRaises(PermissionDenied):
            view(request, author.id)
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

        resp = view(request, author.id)
        author.refresh_from_db()
        self.assertEqual(author.name, "Test Author")
        resp.render()
        self.assertEqual(resp.status_code, 200)
