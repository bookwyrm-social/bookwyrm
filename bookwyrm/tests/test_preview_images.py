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
    remove_user_preview_image_task,
    save_and_cleanup,
)


# pylint: disable=unused-argument
# pylint: disable=missing-function-docstring
class PreviewImages(TestCase):
    """every response to a get request, html or json"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        avatar_path = pathlib.Path(__file__).parent.joinpath(
            "../static/images/no_cover.jpg"
        )
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            open(avatar_path, "rb") as avatar_file,
        ):
            self.local_user = models.User.objects.create_user(
                "possum@local.com",
                "possum@possum.possum",
                "password",
                local=True,
                localname="possum",
                avatar=SimpleUploadedFile(
                    avatar_path,
                    avatar_file.read(),
                    content_type="image/jpeg",
                ),
            )

        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            open(avatar_path, "rb") as avatar_file,
        ):
            self.remote_user_with_preview = models.User.objects.create_user(
                "badger@your.domain.here",
                "badger@badger.com",
                "badgeword",
                local=False,
                remote_id="https://example.com/users/badger",
                inbox="https://example.com/users/badger/inbox",
                outbox="https://example.com/users/badger/outbox",
                avatar=SimpleUploadedFile(
                    avatar_path,
                    avatar_file.read(),
                    content_type="image/jpeg",
                ),
            )

        self.work = models.Work.objects.create(title="Test Work")
        self.edition = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )

        self.site = models.SiteSettings.objects.create()

        settings.ENABLE_PREVIEW_IMAGES = True

    def test_generate_preview_image(self, *args, **kwargs):
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../static/images/no_cover.jpg"
        )

        texts = {
            "text_one": "Awesome Possum",
            "text_three": "@possum@local.com",
        }

        result = generate_preview_image(texts=texts, picture=image_path, rating=5)
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

    def test_remote_user_preview(self, *args, **kwargs):
        """a remote user doesn’t get a user preview"""
        generate_user_preview_image_task(self.remote_user.id)

        self.remote_user.refresh_from_db()

        self.assertFalse(self.remote_user.preview_image)

    def test_generate_user_preview_images_task(self, *args, **kwargs):
        """test task's external calls"""
        with patch("bookwyrm.preview_images.generate_preview_image") as generate_mock:
            generate_user_preview_image_task(self.local_user.id)
        args = generate_mock.call_args.kwargs
        self.assertEqual(args["texts"]["text_one"], "possum")
        self.assertEqual(args["texts"]["text_three"], f"@possum@{settings.DOMAIN}")

    def test_remove_user_preview_image_task(self, *args, **kwargs):
        """you can delete the preview image for a (remote) user"""
        remove_user_preview_image_task(self.remote_user_with_preview.id)

        self.remote_user_with_preview.refresh_from_db()

        self.assertFalse(self.remote_user_with_preview.preview_image)
