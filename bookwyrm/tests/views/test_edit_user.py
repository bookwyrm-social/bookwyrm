""" test for app action functionality """
import json
import pathlib
from unittest.mock import patch
from PIL import Image

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


class EditUserViews(TestCase):
    """view user and edit profile"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        self.rat = models.User.objects.create_user(
            "rat@local.com", "rat@rat.rat", "password", local=True, localname="rat"
        )
        self.book = models.Edition.objects.create(title="test")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ShelfBook.objects.create(
                book=self.book,
                user=self.local_user,
                shelf=self.local_user.shelf_set.first(),
            )

        models.SiteSettings.objects.create()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_edit_user_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditUser.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_edit_user(self):
        """use a form to update a user"""
        view = views.EditUser.as_view()
        form = forms.EditUserForm(instance=self.local_user)
        form.data["name"] = "New Name"
        form.data["email"] = "wow@email.com"
        form.data["preferred_timezone"] = "UTC"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        self.assertIsNone(self.local_user.name)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)
        self.assertEqual(self.local_user.name, "New Name")
        self.assertEqual(self.local_user.email, "wow@email.com")

    def test_edit_user_avatar(self):
        """use a form to update a user"""
        view = views.EditUser.as_view()
        form = forms.EditUserForm(instance=self.local_user)
        form.data["name"] = "New Name"
        form.data["email"] = "wow@email.com"
        form.data["preferred_timezone"] = "UTC"
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/no_cover.jpg"
        )
        form.data["avatar"] = SimpleUploadedFile(
            image_file, open(image_file, "rb").read(), content_type="image/jpeg"
        )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)
        self.assertEqual(self.local_user.name, "New Name")
        self.assertEqual(self.local_user.email, "wow@email.com")
        self.assertIsNotNone(self.local_user.avatar)
        self.assertEqual(self.local_user.avatar.width, 120)
        self.assertEqual(self.local_user.avatar.height, 120)

    def test_crop_avatar(self):
        """reduce that image size"""
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/no_cover.jpg"
        )
        image = Image.open(image_file)

        result = views.edit_user.crop_avatar(image)
        self.assertIsInstance(result, ContentFile)
        image_result = Image.open(result)
        self.assertEqual(image_result.size, (120, 120))

    def test_delete_user_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DeleteUser.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_delete_user(self):
        """use a form to update a user"""
        view = views.DeleteUser.as_view()
        form = forms.DeleteUserForm()
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.local_user
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        self.assertIsNone(self.local_user.name)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            view(request)
        self.assertEqual(delay_mock.call_count, 1)
        activity = json.loads(delay_mock.call_args[0][1])
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(
            activity["cc"][0], "https://www.w3.org/ns/activitystreams#Public"
        )

        self.local_user.refresh_from_db()
        self.assertFalse(self.local_user.is_active)
        self.assertEqual(self.local_user.deactivation_reason, "self_deletion")
