"""test for app action functionality"""

import pathlib
from unittest.mock import patch
from PIL import Image

from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.suggested_users.remove_user_task.delay")
class EditUserViews(TestCase):
    """view user and edit profile"""

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
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
            cls.rat = models.User.objects.create_user(
                "rat@local.com", "rat@rat.rat", "password", local=True, localname="rat"
            )

            cls.book = models.Edition.objects.create(
                title="test", parent_work=models.Work.objects.create(title="test work")
            )
            with (
                patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
                patch("bookwyrm.activitystreams.add_book_statuses_task.delay"),
            ):
                models.ShelfBook.objects.create(
                    book=cls.book,
                    user=cls.local_user,
                    shelf=cls.local_user.shelf_set.first(),
                )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_edit_user_page(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditUser.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_edit_user(self, _):
        """use a form to update a user"""
        view = views.EditUser.as_view()
        form = forms.EditUserForm(instance=self.local_user)
        form.data["name"] = "New Name"
        form.data["email"] = "wow@email.com"
        form.data["default_post_privacy"] = "public"
        form.data["preferred_timezone"] = "UTC"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        self.assertIsNone(self.local_user.name)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)
        self.assertEqual(self.local_user.name, "New Name")
        self.assertEqual(self.local_user.email, "wow@email.com")

    def test_edit_user_avatar(self, _):
        """use a form to update a user"""
        view = views.EditUser.as_view()
        form = forms.EditUserForm(instance=self.local_user)
        form.data["name"] = "New Name"
        form.data["email"] = "wow@email.com"
        form.data["default_post_privacy"] = "public"
        form.data["preferred_timezone"] = "UTC"
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../../static/images/no_cover.jpg"
        )
        with open(image_path, "rb") as image_file:
            form.data["avatar"] = SimpleUploadedFile(
                image_path, image_file.read(), content_type="image/jpeg"
            )
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)
        self.assertEqual(self.local_user.name, "New Name")
        self.assertEqual(self.local_user.email, "wow@email.com")
        self.assertIsNotNone(self.local_user.avatar)
        self.assertEqual(self.local_user.avatar.width, 120)
        self.assertEqual(self.local_user.avatar.height, 120)

    def test_crop_avatar(self, _):
        """reduce that image size"""
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../../static/images/no_cover.jpg"
        )

        with Image.open(image_path) as image:
            result = views.preferences.edit_user.crop_avatar(image)
        self.assertIsInstance(result, ContentFile)
        with Image.open(result) as image_result:
            self.assertEqual(image_result.size, (120, 120))
