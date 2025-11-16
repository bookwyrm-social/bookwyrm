""" test searching for books """
import os
import re
from io import BytesIO
from PIL import Image

from django.core.files import temp as tempfile
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.test import TestCase

from bookwyrm.settings import BASE_URL
from bookwyrm.utils import regex
from bookwyrm.utils.images import remove_uploaded_image_exif
from bookwyrm.utils.validate import validate_url_domain


class TestUtils(TestCase):
    """utility functions"""

    def test_regex(self):
        """Regexes used throughout the app"""
        self.assertTrue(re.match(regex.DOMAIN, "xn--69aa8bzb.xn--y9a3aq"))

    def test_valid_url_domain(self):
        """Check with a valid URL"""
        legit = f"{BASE_URL}/legit-book-url/"
        self.assertEqual(validate_url_domain(legit), legit)

    def test_invalid_url_domain(self):
        """Check with an invalid URL"""
        self.assertIsNone(
            validate_url_domain("https://up-to-no-good.tld/bad-actor.exe")
        )

    def test_remove_uploaded_image_inmemory_exif(self):
        """Check that EXIF data is removed from image"""
        image_path = "bookwyrm/tests/data/default_avi_exif.jpg"
        with open(image_path, "rb") as image_file:
            source = InMemoryUploadedFile(
                BytesIO(image_file.read()),
                "cover",
                "default_avi_exif.jpg",
                "image/jpeg",
                os.fstat(image_file.fileno()).st_size,
                None,
            )
        result = remove_uploaded_image_exif(source)
        with Image.open(result) as image:
            self.assertNotIn("exif", image.info)

    def test_remove_uploaded_image_temporary_exif(self):
        """Check that EXIF data is removed from image"""
        image_path = "bookwyrm/tests/data/default_avi_exif.jpg"
        temporary_file = tempfile.NamedTemporaryFile(mode="w+b", suffix=".jpg")
        with open(image_path, "rb") as image_file:
            temporary_file.write(image_file.read())
            temporary_file.seek(0)
        source = TemporaryUploadedFile(
            temporary_file.name,
            "image/jpeg",
            os.fstat(temporary_file.fileno()).st_size,
            None,
        )
        source.file = temporary_file
        result = remove_uploaded_image_exif(source)
        with Image.open(result) as image:
            self.assertNotIn("exif", image.info)
