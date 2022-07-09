""" test searching for books """
import re
from django.test import TestCase

from bookwyrm.utils import regex


class TestUtils(TestCase):
    """utility functions"""

    def test_regex(self):
        """Regexes used throughout the app"""
        self.assertTrue(re.match(regex.DOMAIN, "xn--69aa8bzb.xn--y9a3aq"))
