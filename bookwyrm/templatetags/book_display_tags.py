"""template filters"""

from django import template
from django.core.exceptions import FieldError
from bookwyrm import models


register = template.Library()


@register.filter(name="review_count")
def get_review_count(book):
    """how many reviews?"""
    return models.Review.objects.filter(deleted=False, book=book).count()


@register.filter(name="book_description")
def get_book_description(book):
    """use the work's text if the book doesn't have it"""
    if book.description:
        return book.description
    if book.parent_work:
        # this should always be true
        return book.parent_work.description
    return None


@register.simple_tag(takes_context=False)
def get_book_file_links(book):
    """links for a book"""
    return book.file_links.filter(domain__status="approved")


@register.filter(name="author_edition")
def get_author_edition(book, author):
    """default edition for a book on the author page"""
    return book.author_edition(author)


@register.filter(name="blocked_book_filter")
def blocked_book_filter(queryset, viewer):
    """filter out blocked books from querysets with editions as 'book'"""

    if not viewer or not viewer.is_authenticated:
        return queryset

    blocked = viewer.blocked_books.all().values_list("id", flat=True)
    try:
        return queryset.exclude(book__parent_work__in=blocked)
    except FieldError:
        pass

    try:
        return queryset.exclude(work__in=blocked)
    except FieldError:
        return queryset.exclude(edition__parent_work__in=blocked)
