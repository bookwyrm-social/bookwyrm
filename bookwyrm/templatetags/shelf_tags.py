""" Filters and tags related to shelving books """
from typing import Any
from django import template
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrPromise

from bookwyrm import models
from bookwyrm.utils import cache


register = template.Library()


SHELF_NAMES = {
    "all": _("All books"),
    "to-read": _("To Read"),
    "reading": _("Currently Reading"),
    "read": _("Read"),
    "stopped-reading": _("Stopped Reading"),
}


@register.filter(name="is_book_on_shelf")
def get_is_book_on_shelf(book: models.Edition, shelf: models.Shelf) -> Any:
    """is a book on a shelf"""
    return cache.get_or_set(
        f"book-on-shelf-{book.id}-{shelf.id}",
        lambda b, s: s.books.filter(id=b.id).exists(),
        book,
        shelf,
        timeout=60 * 60,  # just cache this for an hour
    )


@register.filter(name="next_shelf")
def get_next_shelf(current_shelf: str) -> str:
    """shelf you'd use to update reading progress"""
    if current_shelf == "to-read":
        return "reading"
    if current_shelf == "reading":
        return "read"
    if current_shelf == "read":
        return "complete"
    if current_shelf == "stopped-reading":
        return "stopped-reading-complete"
    return "to-read"


@register.filter(name="translate_shelf_name")
def get_translated_shelf_name(shelf: models.Shelf | dict[str, str]) -> str | StrPromise:
    """produce translated shelf identifiername"""
    if not shelf:
        return ""
    # support obj or dict
    identifier = shelf["identifier"] if isinstance(shelf, dict) else shelf.identifier

    try:
        return SHELF_NAMES[identifier]
    except KeyError:
        return shelf["name"] if isinstance(shelf, dict) else shelf.name


@register.simple_tag(takes_context=True)
def active_shelf(context: dict[str, Any], book: models.Edition) -> Any:
    """check what shelf a user has a book on, if any"""
    user = context["request"].user
    return cache.get_or_set(
        f"active_shelf-{user.id}-{book.id}",
        lambda u, b: (
            models.ShelfBook.objects.filter(
                shelf__user=u,
                book__parent_work__editions=b,
            ).first()
            or False
        ),
        user,
        book,
        timeout=60 * 60,
    ) or {"book": book}


@register.simple_tag(takes_context=False)
def latest_read_through(book: models.Edition, user: models.User) -> Any:
    """the most recent read activity"""
    return cache.get_or_set(
        f"latest_read_through-{user.id}-{book.id}",
        lambda u, b: (
            models.ReadThrough.objects.filter(user=u, book=b, is_active=True)
            .order_by("-start_date")
            .first()
            or False
        ),
        user,
        book,
        timeout=60 * 60,
    )
