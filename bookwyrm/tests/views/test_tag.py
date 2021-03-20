""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse


class TagViews(TestCase):
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

    def test_tag_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Tag.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            tag = models.Tag.objects.create(name="hi there")
            models.UserTag.objects.create(tag=tag, user=self.local_user, book=self.book)
        request = self.factory.get("")
        with patch("bookwyrm.views.tag.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, tag.identifier)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get("")
        with patch("bookwyrm.views.tag.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, tag.identifier)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_tag_page_activitypub_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Tag.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            tag = models.Tag.objects.create(name="hi there")
            models.UserTag.objects.create(tag=tag, user=self.local_user, book=self.book)
        request = self.factory.get("", {"page": 1})
        with patch("bookwyrm.views.tag.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, tag.identifier)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_tag(self):
        """ add a tag to a book """
        view = views.AddTag.as_view()
        request = self.factory.post(
            "",
            {
                "name": "A Tag!?",
                "book": self.book.id,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request)

        tag = models.Tag.objects.get()
        user_tag = models.UserTag.objects.get()
        self.assertEqual(tag.name, "A Tag!?")
        self.assertEqual(tag.identifier, "A+Tag%21%3F")
        self.assertEqual(user_tag.user, self.local_user)
        self.assertEqual(user_tag.book, self.book)

    def test_untag(self):
        """ remove a tag from a book """
        view = views.RemoveTag.as_view()
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            tag = models.Tag.objects.create(name="A Tag!?")
            models.UserTag.objects.create(user=self.local_user, book=self.book, tag=tag)
        request = self.factory.post(
            "",
            {
                "user": self.local_user.id,
                "book": self.book.id,
                "name": tag.name,
            },
        )
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request)

        self.assertTrue(models.Tag.objects.filter(name="A Tag!?").exists())
        self.assertFalse(models.UserTag.objects.exists())
