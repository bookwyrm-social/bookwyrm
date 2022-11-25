""" template filters """
from django import template


register = template.Library()


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
