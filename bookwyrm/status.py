''' Handle user activity '''
from datetime import datetime
from django.db import IntegrityError

from bookwyrm import models
from bookwyrm.books_manager import get_or_create_book
from bookwyrm.sanitize_html import InputHtmlParser


def delete_status(status):
    ''' replace the status with a tombstone '''
    status.deleted = True
    status.deleted_date = datetime.now()
    status.save()


def create_generated_note(user, content, mention_books=None):
    ''' a note created by the app about user activity '''
    # sanitize input html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    status = models.GeneratedNote.objects.create(
        user=user,
        content=content,
    )

    if mention_books:
        for book in mention_books:
            status.mention_books.add(book)

    return status


def create_tag(user, possible_book, name):
    ''' add a tag to a book '''
    book = get_or_create_book(possible_book)

    try:
        tag = models.Tag.objects.create(name=name, book=book, user=user)
    except IntegrityError:
        return models.Tag.objects.get(name=name, book=book, user=user)
    return tag


def create_notification(user, notification_type, related_user=None, \
        related_book=None, related_status=None, related_import=None):
    ''' let a user know when someone interacts with their content '''
    if user == related_user:
        # don't create notification when you interact with your own stuff
        return
    models.Notification.objects.create(
        user=user,
        related_book=related_book,
        related_user=related_user,
        related_status=related_status,
        related_import=related_import,
        notification_type=notification_type,
    )
