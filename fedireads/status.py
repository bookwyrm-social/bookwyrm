''' Handle user activity '''
from django.db import IntegrityError

from fedireads import models
from fedireads.books_manager import get_or_create_book
from fedireads.sanitize_html import InputHtmlParser


def create_review_from_activity(author, activity):
    ''' parse an activity json blob into a status '''
    book_id = activity['inReplyToBook']
    book_id = book_id.split('/')[-1]
    name = activity.get('name')
    rating = activity.get('rating')
    content = activity.get('content')
    published = activity.get('published')
    remote_id = activity['id']

    book = get_or_create_book(book_id)

    review = create_review(author, book, name, content, rating)
    review.published_date = published
    review.remote_id = remote_id
    review.save()
    return review


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
    book = activity['inReplyToBook']
    book = book.split('/')[-1]
    quote = activity.get('quote')
    content = activity.get('content')
    published = activity.get('published')
    remote_id = activity['id']

    quotation = create_quotation(author, book, content, quote)
    quotation.published_date = published
    quotation.remote_id = remote_id
    quotation.save()
    return quotation


def create_quotation(user, possible_book, content, quote):
    ''' a quotation has been added '''
    # throws a value error if the book is not found
    book = get_or_create_book(possible_book)
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
    book = activity['inReplyToBook']
    book = book.split('/')[-1]
    content = activity.get('content')
    published = activity.get('published')
    remote_id = activity['id']

    comment = create_comment(author, book, content)
    comment.published_date = published
    comment.remote_id = remote_id
    comment.save()
    return comment


def create_comment(user, possible_book, content):
    ''' a book comment has been added '''
    # throws a value error if the book is not found
    book = get_or_create_book(possible_book)
    content = sanitize(content)

    return models.Comment.objects.create(
        user=user,
        book=book,
        content=content,
    )


def create_status_from_activity(author, activity):
    ''' parse a status object out of an activity json blob '''
    content = activity.get('content')
    reply_parent_id = activity.get('inReplyTo')
    reply_parent = get_status(reply_parent_id)

    remote_id = activity['id']
    if models.Status.objects.filter(remote_id=remote_id).count():
        return None
    status = create_status(author, content, reply_parent=reply_parent,
                           remote_id=remote_id)
    status.published_date = activity.get('published')
    status.save()
    return status


def create_favorite_from_activity(user, activity):
    ''' create a new favorite entry '''
    status = get_status(activity['object'])
    remote_id = activity['id']
    try:
        return models.Favorite.objects.create(
            status=status,
            user=user,
            remote_id=remote_id,
        )
    except IntegrityError:
        return models.Favorite.objects.get(status=status, user=user)


def create_boost_from_activity(user, activity):
    ''' create a new boost activity '''
    status = get_status(activity['object'])
    remote_id = activity['id']
    try:
        return models.Boost.objects.create(
            status=status,
            user=user,
            remote_id=remote_id,
        )
    except IntegrityError:
        return models.Boost.objects.get(status=status, user=user)


def get_status(absolute_id):
    ''' find a status in the database '''
    return get_by_absolute_id(absolute_id, models.Status)


def get_favorite(absolute_id):
    ''' find a status in the database '''
    return get_by_absolute_id(absolute_id, models.Favorite)


def get_by_absolute_id(absolute_id, model):
    ''' generalized function to get from a model with a remote_id field '''
    if not absolute_id:
        return None

    # check if it's a remote status
    try:
        return model.objects.get(remote_id=absolute_id)
    except model.DoesNotExist:
        pass

    # try finding a local status with that id
    local_id = absolute_id.split('/')[-1]
    try:
        if hasattr(model.objects, 'select_subclasses'):
            possible_match = model.objects.select_subclasses().get(id=local_id)
        else:
            possible_match = model.objects.get(id=local_id)
    except model.DoesNotExist:
        return None

    # make sure it's not actually a remote status with an id that
    # clashes with a local id
    if possible_match.absolute_id == absolute_id:
        return possible_match
    return None


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
        related_book=None, related_status=None):
    ''' let a user know when someone interacts with their content '''
    if user == related_user:
        # don't create notification when you interact with your own stuff
        return
    models.Notification.objects.create(
        user=user,
        related_book=related_book,
        related_user=related_user,
        related_status=related_status,
        notification_type=notification_type,
    )


def sanitize(content):
    ''' remove invalid html from free text '''
    parser = InputHtmlParser()
    parser.feed(content)
    return parser.get_output()
