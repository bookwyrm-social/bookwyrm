''' Handle user activity '''
from datetime import datetime

from bookwyrm import activitypub, books_manager, models
from bookwyrm.books_manager import get_or_create_book
from bookwyrm.sanitize_html import InputHtmlParser


def delete_status(status):
    ''' replace the status with a tombstone '''
    status.deleted = True
    status.deleted_date = datetime.now()
    status.save()


def create_status(activity):
    ''' unfortunately, it's not QUITE as simple as deserialiing it '''
    # render the json into an activity object
    serializer = activitypub.activity_objects[activity['type']]
    activity = serializer(**activity)
    try:
        model = models.activity_models[activity.type]
    except KeyError:
        # not a type of status we are prepared to deserialize
        return None

    # ignore notes that aren't replies to known statuses
    if activity.type == 'Note':
        reply = models.Status.objects.filter(
            remote_id=activity.inReplyTo
        ).first()
        if not reply:
            return None

    # look up books
    book_urls = []
    if hasattr(activity, 'inReplyToBook'):
        book_urls.append(activity.inReplyToBook)
    if hasattr(activity, 'tag'):
        book_urls += [t['href'] for t in activity.tag if t['type'] == 'Book']
    for remote_id in book_urls:
        books_manager.get_or_create_book(remote_id)

    return activity.to_model(model)


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
