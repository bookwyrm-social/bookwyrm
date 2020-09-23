''' Handle user activity '''
from django.db import IntegrityError

from bookwyrm import models
from bookwyrm.books_manager import get_or_create_book
from bookwyrm.sanitize_html import InputHtmlParser


def create_rating(user, book, rating):
    ''' a review that's just a rating '''
    if not rating or rating < 1 or rating > 5:
        raise ValueError('Invalid rating')
    return models.Review.objects.create(
        user=user,
        book=book,
        rating=rating,
    )


def create_review(user, book, name, content, rating):
    ''' a book review has been added '''
    name = sanitize(name)
    content = sanitize(content)

    # no ratings outside of 0-5
    if rating:
        rating = rating if 1 <= rating <= 5 else None
    else:
        rating = None

    return models.Review.objects.create(
        user=user,
        book=book,
        name=name,
        rating=rating,
        content=content,
    )


def create_quotation_from_activity(author, activity):
    ''' parse an activity json blob into a status '''
    book_id = activity['inReplyToBook']
    book = get_or_create_book(book_id)
    quote = activity.get('quote')
    content = activity.get('content')
    published = activity.get('published')
    remote_id = activity['id']

    quotation = create_quotation(author, book, content, quote)
    quotation.published_date = published
    quotation.remote_id = remote_id
    quotation.save()
    return quotation


def create_quotation(user, book, content, quote):
    ''' a quotation has been added '''
    # throws a value error if the book is not found
    content = sanitize(content)
    quote = sanitize(quote)

    return models.Quotation.objects.create(
        user=user,
        book=book,
        content=content,
        quote=quote,
    )


def create_comment_from_activity(author, activity):
    ''' parse an activity json blob into a status '''
    book_id = activity['inReplyToBook']
    book = get_or_create_book(book_id)
    content = activity.get('content')
    published = activity.get('published')
    remote_id = activity['id']

    comment = create_comment(author, book, content)
    comment.published_date = published
    comment.remote_id = remote_id
    comment.save()
    return comment


def create_comment(user, book, content):
    ''' a book comment has been added '''
    # throws a value error if the book is not found
    content = sanitize(content)

    return models.Comment.objects.create(
        user=user,
        book=book,
        content=content,
    )


def get_status(remote_id):
    ''' find a status in the database '''
    return models.Status.objects.select_subclasses().filter(
        remote_id=remote_id
    ).first()


def create_status(user, content, reply_parent=None, mention_books=None,
                  remote_id=None):
    ''' a status update '''
    # TODO: handle @'ing users

    # sanitize input html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    status = models.Status.objects.create(
        user=user,
        content=content,
        reply_parent=reply_parent,
        remote_id=remote_id,
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


def sanitize(content):
    ''' remove invalid html from free text '''
    parser = InputHtmlParser()
    parser.feed(content)
    return parser.get_output()
