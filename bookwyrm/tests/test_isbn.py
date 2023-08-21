""" test ISBN hyphenator for books """
from django.test import TestCase

from bookwyrm.isbn.isbn import hyphenator_singleton as hyphenator


class TestISBN(TestCase):
    """isbn hyphenator"""

    def test_isbn_hyphenation(self):
        """different isbn hyphenations"""
        # nothing
        self.assertEqual(hyphenator.hyphenate(None), None)
        # 978-0 (English language) 3700000-6389999
        self.assertEqual(hyphenator.hyphenate("9780439554930"), "978-0-439-55493-0")
        # 978-2 (French language) 0000000-1999999
        self.assertEqual(hyphenator.hyphenate("9782070100927"), "978-2-07-010092-7")
        # 978-3 (German language) 2000000-6999999
        self.assertEqual(hyphenator.hyphenate("9783518188125"), "978-3-518-18812-5")
        # 978-4 (Japan) 0000000-1999999
        self.assertEqual(hyphenator.hyphenate("9784101050454"), "978-4-10-105045-4")
        # 978-626 (Taiwan) 9500000-9999999
        self.assertEqual(hyphenator.hyphenate("9786269533251"), "978-626-95332-5-1")
        # 979-8 (United States) 4000000-8499999
        self.assertEqual(hyphenator.hyphenate("9798627974040"), "979-8-6279-7404-0")
        # 978-626 (Taiwan) 8000000-9499999 (unassigned)
        self.assertEqual(hyphenator.hyphenate("9786268533251"), "9786268533251")
        # 978 range 6600000-6999999 (unassigned)
        self.assertEqual(hyphenator.hyphenate("9786769533251"), "9786769533251")
        # 979-8 (United States) 2300000-3499999 (unassigned)
        self.assertEqual(hyphenator.hyphenate("9798311111111"), "9798311111111")
