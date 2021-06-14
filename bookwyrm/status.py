""" Handle user activity """
from django.db import transaction

from bookwyrm import models
from bookwyrm.sanitize_html import InputHtmlParser


def create_generated_note(user, content, mention_books=None, privacy="public"):
    """a note created by the app about user activity"""
    # sanitize input html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    with transaction.atomic():
        # create but don't save
        status = models.GeneratedNote(user=user, content=content, privacy=privacy)
        # we have to save it to set the related fields, but hold off on telling
        # folks about it because it is not ready
        status.save(broadcast=False)

        if mention_books:
            status.mention_books.set(mention_books)
        status.save(created=True)
    return status
