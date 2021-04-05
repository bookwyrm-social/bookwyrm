""" test for app action functionality """
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
from bookwyrm.activitypub import ActivitypubResponse


class UserViews(TestCase):
    """ view user and edit profile """

    def setUp(self):
        """ we need basic test data and mocks """
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
        models.SiteSettings.objects.create()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_user_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_user_page_blocked(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "rat")
        self.assertEqual(result.status_code, 404)

    def test_followers_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Followers.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_followers_page_blocked(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Followers.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "rat")
        self.assertEqual(result.status_code, 404)

    def test_following_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Following.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_following_page_blocked(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Following.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "rat")
        self.assertEqual(result.status_code, 404)

    def test_edit_user_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.EditUser.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_edit_user(self):
        """ use a form to update a user """
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

    # idk how to mock the upload form, got tired of triyng to make it work
    def test_edit_user_avatar(self):
        """ use a form to update a user """
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
        """ reduce that image size """
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/no_cover.jpg"
        )
        image = Image.open(image_file)

        result = views.user.crop_avatar(image)
        self.assertIsInstance(result, ContentFile)
        image_result = Image.open(result)
        self.assertEqual(image_result.size, (120, 120))
