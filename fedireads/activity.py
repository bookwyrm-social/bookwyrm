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

    review = models.Review.objects.create(
        user=user,
        book=book,
        name=name,
        rating=rating,
        content=content,
    )

    return review


