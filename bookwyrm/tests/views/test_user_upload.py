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


class UserUploadViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def test_target_size(self):
        self.assertEqual(views.user_upload.target_size(800, 600, 400), [400, 300])
        self.assertEqual(views.user_upload.target_size(600, 800, 400), [300, 400])
        self.assertEqual(views.user_upload.target_size(1200, 1200, 500), [500, 500])
        self.assertEqual(views.user_upload.target_size(345, 456, 500), [345, 456])

    def test_upload(self):
        view = views.CreateUserUpload.as_view()
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../../static/images/logo.png"
        )
        with patch.dict("os.environ", {"UPLOAD_IMAGE_DIMENSIONS": "120,600"}):
            with open(image_path, "rb") as image_file:
                request = self.factory.post("/upload", {"file": image_file})
                request.user = self.local_user
                response = view(request)
        self.assertEqual(response.status_code, 201)
        upload = self.local_user.user_uploads.get()
        self.assertEqual(upload.original_name, "logo.png")
        versions = [v for v in upload.versions.all()]
        self.assertEqual(len(versions), 2)
        self.assertEqual([v.max_dimension for v in versions], ["120", "600"])
        self.assertEqual(
            [[v.file.height, v.file.width] for v in versions], [[115, 120], [300, 314]]
        )
