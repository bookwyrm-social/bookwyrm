""" test searching for books """
import os
import re
from PIL import Image

from django.core.files.uploadedfile import InMemoryUploadedFile
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

    def test_remove_uploaded_image_exif(self):
        """Check that EXIF data is removed from image"""
        image_path = "bookwyrm/tests/data/default_avi_exif.jpg"
        with open(image_path, "rb") as image_file:
            source = InMemoryUploadedFile(
                image_file,
                "cover",
                "default_avi_exif.jpg",
                "image/jpeg",
                os.fstat(image_file.fileno()).st_size,
                None,
            )
            sanitized_image = Image.open(remove_uploaded_image_exif(source).open())
            self.assertNotIn("exif", sanitized_image.info)
