""" make sure only valid html gets to the app """
from django.test import TestCase

from bookwyrm.utils.sanitizer import clean


class Sanitizer(TestCase):
    """sanitizer tests"""

    def test_no_html(self):
        """just text"""
        input_text = "no      html  "
        output = clean(input_text)
        self.assertEqual(input_text, output)

    def test_valid_html(self):
        """leave the html untouched"""
        input_text = "<b>yes    </b> <i>html</i>"
        output = clean(input_text)
        self.assertEqual(input_text, output)

    def test_valid_html_attrs(self):
        """and don't remove useful attributes"""
        input_text = '<a href="fish.com">yes    </a> <i>html</i>'
        output = clean(input_text)
        self.assertEqual(input_text, output)

    def test_valid_html_invalid_attrs(self):
        """do remove un-approved attributes"""
        input_text = '<a href="fish.com" fish="hello">yes    </a> <i>html</i>'
        output = clean(input_text)
        self.assertEqual(output, '<a href="fish.com">yes    </a> <i>html</i>')

    def test_invalid_html(self):
        """don't allow malformed html"""
        input_text = "<b>yes  <i>html</i>"
        output = clean(input_text)
        self.assertEqual("<b>yes  <i>html</i></b>", output)

        input_text = "yes <i></b>html   </i>"
        output = clean(input_text)
        self.assertEqual("yes <i>html   </i>", output)

    def test_disallowed_html(self):
        """remove disallowed html but keep allowed html"""
        input_text = "<div>  yes <i>html</i></div>"
        output = clean(input_text)
        self.assertEqual("  yes <i>html</i>", output)
