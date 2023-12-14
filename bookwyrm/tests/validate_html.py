""" html validation on rendered templates """
from html.parser import HTMLParser
from tidylib import tidy_document


def validate_html(html):
    """run tidy on html"""
    _, errors = tidy_document(
        html.content,
        options={
            "doctype": "html5",
            "drop-empty-elements": False,
            "warn-proprietary-attributes": False,
        },
    )
    # idk how else to filter out these unescape amp errs
    errors = "\n".join(
        e
        for e in errors.split("\n")
        if "&book" not in e
        and "&type" not in e
        and "&resolved" not in e
        and "id and name attribute" not in e
        and "illegal characters found in URI" not in e
        and "escaping malformed URI reference" not in e
    )
    if errors:
        raise Exception(errors)

    validator = HtmlValidator()
    # will raise exceptions
    validator.feed(str(html.content))


class HtmlValidator(HTMLParser):  # pylint: disable=abstract-method
    """Checks for custom html validation requirements"""

    def __init__(self):
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        """check if the tag is valid"""
        # filter out everything besides links that open in new tabs
        if tag != "a" or ("target", "_blank") not in attrs:
            return

        for attr, value in attrs:
            if (
                attr == "rel"
                and "nofollow" in value
                and "noopener" in value
                and "noreferrer" in value
            ):
                return
        raise Exception(
            'Links to a new tab must have rel="nofollow noopener noreferrer"'
        )
