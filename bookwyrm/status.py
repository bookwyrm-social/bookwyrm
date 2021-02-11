''' Handle user activity '''
from django.utils import timezone

from bookwyrm import models
from bookwyrm.sanitize_html import InputHtmlParser


def delete_status(status):
    ''' replace the status with a tombstone '''
    status.deleted = True
    status.deleted_date = timezone.now()
    status.save()


def create_generated_note(user, content, mention_books=None, privacy='public'):
    ''' a note created by the app about user activity '''
    # sanitize input html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    status = models.GeneratedNote.objects.create(
        user=user,
        content=content,
        privacy=privacy
    )

    if mention_books:
        for book in mention_books:
            status.mention_books.add(book)

    return status
