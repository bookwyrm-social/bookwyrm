""" test generating preview images """
import pathlib
from unittest.mock import patch
from PIL import Image

from django.test import TestCase
from django.test.client import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import ImageFieldFile

from bookwyrm import models, settings

from bookwyrm.preview_images import (
    generate_site_preview_image_task,
    generate_edition_preview_image_task,
    generate_user_preview_image_task,
    generate_preview_image,
    save_and_cleanup,
)


# pylint: disable=unused-argument
# pylint: disable=missing-function-docstring
class PreviewImages(TestCase):
    """every response to a get request, html or json"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.preview_images.generate_user_preview_image_task.delay"):
            avatar_file = pathlib.Path(__file__).parent.joinpath(
                "../static/images/no_cover.jpg"
            )
            self.local_user = models.User.objects.create_user(
                "possum@local.com",
                "possum@possum.possum",
                "password",
                local=True,
                localname="possum",
                avatar=SimpleUploadedFile(
                    avatar_file,
                    open(avatar_file, "rb").read(),
                    content_type="image/jpeg",
                ),
            )
        with patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay"):
            self.work = models.Work.objects.create(title="Test Work")
            self.edition = models.Edition.objects.create(
                title="Example Edition",
                remote_id="https://example.com/book/1",
                parent_work=self.work,
            )
        with patch("bookwyrm.preview_images.generate_site_preview_image_task.delay"):
            self.site = models.SiteSettings.objects.create()

    def test_generate_preview_image(self, *args, **kwargs):
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../static/images/no_cover.jpg"
        )

        texts = {
            "text_one": "Awesome Possum",
            "text_three": "@possum@local.com",
        }

        result = generate_preview_image(texts=texts, picture=image_file, rating=5)
        self.assertIsInstance(result, Image.Image)
        self.assertEqual(
            result.size, (settings.PREVIEW_IMG_WIDTH, settings.PREVIEW_IMG_HEIGHT)
        )

    def test_store_preview_image(self, *args, **kwargs):
        image = Image.new("RGB", (200, 200), color="#F00")

        result = save_and_cleanup(image, instance=self.local_user)
        self.assertTrue(result)

        self.local_user.refresh_from_db()
        self.assertIsInstance(self.local_user.preview_image, ImageFieldFile)
        self.assertIsNotNone(self.local_user.preview_image)
        self.assertEqual(self.local_user.preview_image.width, 200)
        self.assertEqual(self.local_user.preview_image.height, 200)

    def test_site_preview(self, *args, **kwargs):
        """generate site preview"""
        generate_site_preview_image_task()

        self.site.refresh_from_db()

        self.assertIsInstance(self.site.preview_image, ImageFieldFile)
        self.assertIsNotNone(self.site.preview_image)
        self.assertEqual(self.site.preview_image.width, settings.PREVIEW_IMG_WIDTH)
        self.assertEqual(self.site.preview_image.height, settings.PREVIEW_IMG_HEIGHT)

    def test_edition_preview(self, *args, **kwargs):
        """generate edition preview"""
        generate_edition_preview_image_task(self.edition.id)

        self.edition.refresh_from_db()

        self.assertIsInstance(self.edition.preview_image, ImageFieldFile)
        self.assertIsNotNone(self.edition.preview_image)
        self.assertEqual(self.edition.preview_image.width, settings.PREVIEW_IMG_WIDTH)
        self.assertEqual(self.edition.preview_image.height, settings.PREVIEW_IMG_HEIGHT)

    def test_user_preview(self, *args, **kwargs):
        """generate user preview"""
        generate_user_preview_image_task(self.local_user.id)

        self.local_user.refresh_from_db()

        self.assertIsInstance(self.local_user.preview_image, ImageFieldFile)
        self.assertIsNotNone(self.local_user.preview_image)
        self.assertEqual(
            self.local_user.preview_image.width, settings.PREVIEW_IMG_WIDTH
        )
        self.assertEqual(
            self.local_user.preview_image.height, settings.PREVIEW_IMG_HEIGHT
        )
