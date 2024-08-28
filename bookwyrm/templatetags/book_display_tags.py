""" template filters """
from typing import Any
from django import template
from django.db.models import QuerySet
from bookwyrm import models


register = template.Library()


@register.filter(name="review_count")
def get_review_count(book: models.Edition) -> int:
    """how many reviews?"""
    return models.Review.objects.filter(deleted=False, book=book).count()


@register.filter(name="book_description")
def get_book_description(book: models.Edition) -> Any:
    """use the work's text if the book doesn't have it"""
    if book.description:
        return book.description
    if book.parent_work:
        # this should always be true
        return book.parent_work.description
    return None


@register.simple_tag(takes_context=False)
def get_book_file_links(book: models.Edition) -> QuerySet[models.FileLink]:
    """links for a book"""
    return book.file_links.filter(domain__status="approved")


@register.filter(name="author_edition")
def get_author_edition(book: models.Work, author: models.Author) -> Any:
    """default edition for a book on the author page"""
    return book.author_edition(author)
