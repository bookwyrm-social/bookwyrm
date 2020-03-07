''' Handle user activity '''
from fedireads import models
from fedireads.openlibrary import get_or_create_book
from fedireads.sanitize_html import InputHtmlParser
from django.db import IntegrityError


def create_review(user, possible_book, name, content, rating, published):
    ''' a book review has been added '''
    # throws a value error if the book is not found
    book = get_or_create_book(possible_book)

    content = sanitize(content)

    # no ratings outside of 0-5
    rating = rating if 0 <= rating <= 5 else 0

    return models.Review.objects.create(
        user=user,
        book=book,
        name=name,
        rating=rating,
        content=content,
        published_date=published,
    )


def create_status(user, content, reply_parent=None, mention_books=None):
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


def sanitize(content):
    ''' remove invalid html from free text '''
    parser = InputHtmlParser()
    parser.feed(content)
    return parser.get_output()
