""" test searching for books """
import re
from django.test import TestCase

from bookwyrm.settings import BASE_URL
from bookwyrm.utils import regex
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
