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
    # Tidy's parser is strict when validating unescaped/encoded ampersands found within
    # the html document that are notpart of a character or entity reference
    # (eg: `&amp;` or `&#38`). Despite the fact the HTML5 spec no longer recommends
    # escaping ampersands in URLs, Tidy will still complain if they are used as query
    # param keys. Unfortunately, there is no way currently to configure tidy to ignore
    # this so we must explictly redlist related strings that will appear in Tidy's
    # errors output.
    #
    # See further discussion: https://github.com/htacg/tidy-html5/issues/1017
    excluded = [
        "&book",
        "&type",
        "&resolved",
        "id and name attribute",
        "illegal characters found in URI",
        "escaping malformed URI reference",
        "&filter",
    ]
    errors = "\n".join(
        e for e in errors.split("\n") if not any(exclude in e for exclude in excluded)
    )
    if errors:
        raise ValueError(errors)

    validator = HtmlValidator()
    # will raise exceptions
    validator.feed(str(html.content))


class HtmlValidator(HTMLParser):
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
        raise ValueError(
            'Links to a new tab must have rel="nofollow noopener noreferrer"'
        )
