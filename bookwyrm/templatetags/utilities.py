""" template filters for really common utilities """
from uuid import uuid4
from django import template


register = template.Library()


@register.filter(name="uuid")
def get_uuid(identifier):
    """for avoiding clashing ids when there are many forms"""
    return "%s%s" % (identifier, uuid4())


@register.filter(name="username")
def get_user_identifier(user):
    """use localname for local users, username for remote"""
    return user.localname if user.localname else user.username


@register.filter(name="book_title")
def get_title(book):
    """display the subtitle if the title is short"""
    if not book:
        return ""
    title = book.title
    if len(title) < 6 and book.subtitle:
        title = "{:s}: {:s}".format(title, book.subtitle)
    return title


@register.simple_tag(takes_context=False)
def comparison_bool(str1, str2):
    """idk why I need to write a tag for this, it reutrns a bool"""
    return str1 == str2
