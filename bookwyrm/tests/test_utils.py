""" test searching for books """
import re
from django.test import TestCase

from bookwyrm.utils import regex
from bookwyrm.utils.validate import validate_url_domain


class TestUtils(TestCase):
    """utility functions"""

    def test_regex(self):
        """Regexes used throughout the app"""
        self.assertTrue(re.match(regex.DOMAIN, "xn--69aa8bzb.xn--y9a3aq"))

    def test_valid_url_domain(self):
        """Check with a valid URL"""
        self.assertEqual(
            validate_url_domain("https://your.domain.here/legit-book-url/"),
            "https://your.domain.here/legit-book-url/",
        )

    def test_invalid_url_domain(self):
        """Check with an invalid URL"""
        self.assertIsNone(
            validate_url_domain("https://up-to-no-good.tld/bad-actor.exe")
        )

    def test_default_url_domain(self):
        """Check with a default URL"""
        self.assertEqual(validate_url_domain("/"), "/")
