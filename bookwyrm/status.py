''' Handle user activity '''
from django.db import transaction
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

    with transaction.atomic():
        # create but don't save
        status = models.GeneratedNote(
            user=user,
            content=content,
            privacy=privacy
        )
        # we have to save it to set the related fields, but hold off on telling
        # folks about it because it is not ready
        status.save(broadcast=False)

        if mention_books:
            status.mention_books.set(mention_books)
        status.save(created=True)
    return status


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
