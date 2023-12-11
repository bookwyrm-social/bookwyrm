""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


class LinkViews(TestCase):
    """books books books"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        group = Group.objects.create(name="editor")
        group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )
        self.local_user.groups.add(group)

        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_add_link_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.AddFileLink.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)

    def test_add_link_post(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.AddFileLink.as_view()
        form = forms.FileLinkForm()
        form.data["url"] = "https://www.example.com"
        form.data["filetype"] = "HTML"
        form.data["book"] = self.book.id
        form.data["added_by"] = self.local_user.id
        form.data["availability"] = "loan"

        request = self.factory.post("", form.data)
        request.user = self.local_user
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as mock:
            view(request, self.book.id)
        self.assertEqual(mock.call_count, 1)

        activity = json.loads(mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Update")
        self.assertEqual(activity["object"]["type"], "Edition")
        self.assertIsInstance(activity["object"]["fileLinks"], list)
        self.assertEqual(
            activity["object"]["fileLinks"][0]["href"], "https://www.example.com"
        )
        self.assertEqual(activity["object"]["fileLinks"][0]["mediaType"], "HTML")
        self.assertEqual(
            activity["object"]["fileLinks"][0]["attributedTo"],
            self.local_user.remote_id,
        )

        link = models.FileLink.objects.get()
        self.assertEqual(link.name, "www.example.com")
        self.assertEqual(link.url, "https://www.example.com")
        self.assertEqual(link.filetype, "HTML")

        self.book.refresh_from_db()
        self.assertEqual(self.book.file_links.first(), link)

    def test_book_links(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.BookFileLinks.as_view()
        models.FileLink.objects.create(
            book=self.book,
            added_by=self.local_user,
            url="https://www.hello.com",
        )
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, self.book.id)
        self.assertEqual(result.status_code, 200)
        validate_html(result.render())

    def test_book_links_post(self):
        """there are so many views, this just makes sure it LOADS"""
        link = models.FileLink.objects.create(
            book=self.book,
            added_by=self.local_user,
            url="https://www.hello.com",
        )
        view = views.BookFileLinks.as_view()
        form = forms.FileLinkForm()
        form.data["url"] = link.url
        form.data["filetype"] = "HTML"
        form.data["book"] = self.book.id
        form.data["added_by"] = self.local_user.id
        form.data["availability"] = "loan"

        request = self.factory.post("", form.data)
        request.user = self.local_user
        view(request, self.book.id, link.id)

        link.refresh_from_db()
        self.assertEqual(link.filetype, "HTML")
        self.assertEqual(link.availability, "loan")

    def test_delete_link(self):
        """remove a link"""
        link = models.FileLink.objects.create(
            book=self.book,
            added_by=self.local_user,
            url="https://www.hello.com",
        )
        form = forms.FileLinkForm()
        form.data["url"] = "https://www.example.com"
        form.data["filetype"] = "HTML"
        form.data["book"] = self.book.id
        form.data["added_by"] = self.local_user.id
        form.data["availability"] = "loan"

        request = self.factory.post("", form.data)
        request.user = self.local_user
        views.delete_link(request, self.book.id, link.id)
        self.assertFalse(models.FileLink.objects.exists())
