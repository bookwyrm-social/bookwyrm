""" make sure only valid html gets to the app """
from django.test import TestCase

from bookwyrm.sanitize_html import InputHtmlParser


class Sanitizer(TestCase):
    """sanitizer tests"""

    def test_no_html(self):
        """just text"""
        input_text = "no      html  "
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)

    def test_valid_html(self):
        """leave the html untouched"""
        input_text = "<b>yes    </b> <i>html</i>"
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)

    def test_valid_html_attrs(self):
        """and don't remove attributes"""
        input_text = '<a href="fish.com">yes    </a> <i>html</i>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)

    def test_invalid_html(self):
        """remove all html when the html is malformed"""
        input_text = "<b>yes  <i>html</i>"
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual("yes  html", output)

        input_text = "yes <i></b>html   </i>"
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual("yes html   ", output)

    def test_disallowed_html(self):
        """remove disallowed html but keep allowed html"""
        input_text = "<div>  yes <i>html</i></div>"
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual("  yes <i>html</i>", output)
