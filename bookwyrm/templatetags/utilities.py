""" template filters for really common utilities """
import os
from uuid import uuid4
from django import template
from django.utils.translation import gettext_lazy as _


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
def get_title(book, too_short=5):
    """display the subtitle if the title is short"""
    if not book:
        return ""
    title = book.title
    if len(title) <= too_short and book.subtitle:
        title = _("%(title)s: %(subtitle)s") % {
            "title": title,
            "subtitle": book.subtitle,
        }
    return title


@register.simple_tag(takes_context=False)
def comparison_bool(str1, str2):
    """idk why I need to write a tag for this, it reutrns a bool"""
    return str1 == str2


@register.filter(is_safe=True)
def truncatepath(value, arg):
    """Truncate a path by removing all directories except the first and truncating ."""
    path = os.path.normpath(value.name)
    path_list = path.split(os.sep)
    try:
        length = int(arg)
    except ValueError:  # invalid literal for int()
        return path_list[-1]  # Fail silently.
    return "%s/…%s" % (path_list[0], path_list[-1][-length:])
