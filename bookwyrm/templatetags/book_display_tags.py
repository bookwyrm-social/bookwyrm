""" template filters """
from django import template
import humanize

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
        # this shoud always be true
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


@register.filter(name="localized_duration")
def get_localized_duration(duration):
    """Returns a localized version of the play time"""

    return humanize.precisedelta(duration)


@register.filter(name="iso_duration")
def get_iso_duration(duration):
    """Returns an ISO8601 version of the play time"""
    duration = str(duration).split(":")

    iso_string = ["PT"]
    if int(duration[0]) > 0:
        iso_string.append(f"{str(duration[0]).zfill(2)}H")

    iso_string.append(f"{str(duration[1]).zfill(2)}M")

    return "".join(iso_string)
