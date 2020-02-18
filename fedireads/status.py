''' Handle user activity '''
from fedireads import models
from fedireads.openlibrary import get_or_create_book
from fedireads.sanitize_html import InputHtmlParser


def create_review(user, possible_book, name, content, rating):
    ''' a book review has been added '''
    # throws a value error if the book is not found
    book = get_or_create_book(possible_book)

    # sanitize review html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    # no ratings outside of 0-5
    rating = rating if 0 <= rating <= 5 else 0

    return models.Review.objects.create(
        user=user,
        book=book,
        name=name,
        rating=rating,
        content=content,
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

    for book in mention_books:
        status.mention_books.add(book)

    return status

