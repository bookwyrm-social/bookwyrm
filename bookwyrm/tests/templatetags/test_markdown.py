""" style fixes and lookups for templates """
from django.test import TestCase
from bookwyrm.templatetags import markdown


class MarkdownTags(TestCase):
    """lotta different things here"""

    def test_get_markdown(self):
        """mardown format data"""
        result = markdown.get_markdown("_hi_")
        self.assertEqual(result, "<p><em>hi</em></p>")

        result = markdown.get_markdown("<marquee>_hi_</marquee>")
        self.assertEqual(result, "<p><em>hi</em></p>")
