""" html validation on rendered templates """
from tidylib import tidy_document


def validate_html(html):
    """run tidy on html"""
    _, errors = tidy_document(
        html.content,
        options={
            "drop-empty-elements": False,
            "warn-proprietary-attributes": False,
        },
    )
    # idk how else to filter out these unescape amp errs
    errors = "\n".join(
        e
        for e in errors.split("\n")
        if "&book" not in e and "id and name attribute" not in e
    )
    if errors:
        raise Exception(errors)
