""" template filters for list page """
from django import template
from django.utils.translation import gettext_lazy as _, ngettext

from bookwyrm import models


register = template.Library()


@register.filter(name="opengraph_title")
def get_opengraph_title(book_list: models.List) -> str:
    """Construct title for Open Graph"""
    return _("Book List: %(name)s") % {"name": book_list.name}


@register.filter(name="opengraph_description")
def get_opengraph_description(book_list: models.List) -> str:
    """Construct description for Open Graph"""
    num_books = book_list.books.all().count()
    num_books_str = ngettext(
        "%(num)d book - by %(user)s", "%(num)d books - by %(user)s", num_books
    ) % {"num": num_books, "user": book_list.user}

    return f"{book_list.description} {num_books_str}"
