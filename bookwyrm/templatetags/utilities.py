""" template filters for really common utilities """
from typing import Any, Optional

import os
import re
from uuid import uuid4
from urllib.parse import urlparse
from django import template
from django.contrib.auth.models import Group
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.templatetags.static import static
from django_stubs_ext import StrPromise

from bookwyrm.models import Author, Edition, User
from bookwyrm.settings import INSTANCE_ACTOR_USERNAME

register = template.Library()


@register.filter(name="uuid")
def get_uuid(identifier: str) -> str:
    """for avoiding clashing ids when there are many forms"""
    return f"{identifier}{uuid4()}"


@register.simple_tag(takes_context=False)
def join(*args: tuple[Any]) -> str:
    """concatenate an arbitrary set of values"""
    return "_".join(str(a) for a in args)


@register.filter(name="username")
def get_user_identifier(user: User) -> str:
    """use localname for local users, username for remote"""
    return user.localname if user.localname else user.username or ""


@register.filter(name="user_from_remote_id")
def get_user_identifier_from_remote_id(remote_id: str) -> Optional[User]:
    """get the local user id from their remote id"""
    user = User.objects.get(remote_id=remote_id)
    return user if user else None


@register.filter(name="book_title")
def get_title(book: Edition, too_short: int = 5) -> Any:
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
def comparison_bool(str1: str, str2: str, reverse: bool = False) -> bool:
    """idk why I need to write a tag for this, it returns a bool"""
    if reverse:
        return str1 != str2
    return str1 == str2


@register.filter(is_safe=True)
def truncatepath(value: Any, arg: Any) -> Any:
    """Truncate a path by removing all directories except the first and truncating"""
    path = os.path.normpath(value.name)
    path_list = path.split(os.sep)
    try:
        length = int(arg)
    except ValueError:  # invalid literal for int()
        return path_list[-1]  # Fail silently.
    return f"{path_list[0]}/…{path_list[-1][-length:]}"


@register.simple_tag(takes_context=False)
def get_book_cover_thumbnail(
    book: Edition, size: str = "medium", ext: str = "jpg"
) -> Any:
    """Returns a book thumbnail at the specified size and extension,
    with fallback if needed"""
    if size == "":
        size = "medium"
    try:
        cover_thumbnail = getattr(book, f"cover_bw_book_{size}_{ext}")
        return cover_thumbnail.url
    except OSError:
        return static("images/no_cover.jpg")


@register.filter(name="get_isni_bio")
def get_isni_bio(existing: int, author: Author) -> str:
    """Returns the isni bio string if an existing author has an isni listed"""
    auth_isni = re.sub(r"\D", "", str(author.isni))
    if len(existing) == 0:
        return ""
    for value in existing:
        if hasattr(value, "bio") and auth_isni == re.sub(r"\D", "", str(value.isni)):
            return mark_safe(f"Author of <em>{value.bio}</em>")

    return ""


# pylint: disable=unused-argument
@register.filter(name="get_isni", needs_autoescape=True)
def get_isni(existing: str, author: Author, autoescape: bool = True) -> str:
    """Returns the isni ID if an existing author has an ISNI listing"""
    auth_isni = re.sub(r"\D", "", str(author.isni))
    if len(existing) == 0:
        return ""
    for value in existing:
        if hasattr(value, "isni") and auth_isni == re.sub(r"\D", "", str(value.isni)):
            isni = value.isni
            return mark_safe(
                f'<input type="text" name="isni-for-{author.id}" value="{isni}" hidden>'
            )
    return ""


@register.simple_tag(takes_context=False)
def id_to_username(user_id: str) -> str | StrPromise:
    """given an arbitrary remote id, return the username"""
    if user_id:
        url = urlparse(user_id)
        domain = url.hostname
        parts = url.path.split("/")
        name = parts[-1]
        value = f"{name}@{domain}"

        return value
    return _("a new user account")


@register.filter(name="get_file_size")
def get_file_size(nbytes: int) -> str:
    """display the size of a file in human readable terms"""

    try:
        raw_size = float(nbytes)
    except (ValueError, TypeError):
        return repr(nbytes)

    if raw_size < 1024:
        return f"{raw_size} bytes"
    if raw_size < 1024**2:
        return f"{raw_size/1024:.2f} KB"
    if raw_size < 1024**3:
        return f"{raw_size/1024**2:.2f} MB"
    return f"{raw_size/1024**3:.2f} GB"


@register.filter(name="get_user_permission")
def get_user_permission(user: User) -> Group | str:
    """given a user, return their permission level"""

    return user.groups.first() or "User"


@register.filter(name="is_instance_admin")
def is_instance_admin(localname: str) -> bool:
    """Returns a boolean indicating whether the user is the instance admin account"""
    return localname == INSTANCE_ACTOR_USERNAME
