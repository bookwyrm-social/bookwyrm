from django.test import TestCase

from bookwyrm.sanitize_html import InputHtmlParser


class Sanitizer(TestCase):
    def test_no_html(self):
        input_text = 'no      html  '
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)


    def test_valid_html(self):
        input_text = '<b>yes    </b> <i>html</i>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)


    def test_valid_html_attrs(self):
        input_text = '<a href="fish.com">yes    </a> <i>html</i>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual(input_text, output)


    def test_invalid_html(self):
        input_text = '<b>yes  <i>html</i>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual('yes  html', output)

        input_text = 'yes <i></b>html   </i>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual('yes html   ', output)


    def test_disallowed_html(self):
        input_text = '<div>  yes <i>html</i></div>'
        parser = InputHtmlParser()
        parser.feed(input_text)
        output = parser.get_output()
        self.assertEqual('  yes <i>html</i>', output)
