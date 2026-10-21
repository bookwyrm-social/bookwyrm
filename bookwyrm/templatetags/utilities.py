"""template filters for really common utilities"""

import os
from typing import Any, List

from uuid import uuid4
from urllib.parse import urlparse
from django import template
from django.contrib.auth.models import Group
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.templatetags.static import static

from bookwyrm.models import User, Book, SeriesBook
from bookwyrm.settings import INSTANCE_ACTOR_USERNAME, DATA_UPLOAD_MAX_MEMORY_SIZE

register = template.Library()


@register.filter(name="uuid")
def get_uuid(identifier: str) -> str:
    """for avoiding clashing ids when there are many forms"""
    return f"{identifier}{uuid4()}"


@register.simple_tag(takes_context=False)
def join(*args: Any) -> str:
    """concatenate an arbitrary set of values"""
    return "_".join(str(a) for a in args)


@register.filter(name="getattr_filter")
def getattr_filter(obj: Any, arg: str) -> Any:
    """get attribute value from an object"""

    if obj.__class__._meta.get_field(arg).get_internal_type() == "ArrayField":
        return getattr(obj, arg, [])
    if obj.__class__._meta.get_field(arg).get_internal_type() == "DateTimeField":
        if getattr(obj, arg) is not None:
            return getattr(obj, arg).strftime("%Y-%m-%d")
        return ""

    return getattr(object, arg, "") or ""


@register.filter(name="username")
def get_user_identifier(user: User) -> Any:
    """use localname for local users, username for remote"""
    return user.localname if user.localname else user.username


@register.filter(is_safe=True)
@register.filter(name="user_link")
def get_link_to_user(user: User) -> str:
    """get a link to a user profile, or display if the user has been deleted"""
    username = user.display_name
    if user.is_active:
        return mark_safe(f'<a href="{user.local_path}">{username}</a>')
    text = _("deactivated user")
    return mark_safe(f"<em class='tag'>{text}</em>")


@register.filter(name="user_from_remote_id")
def get_user_identifier_from_remote_id(remote_id: str) -> User | None:
    """get the local user id from their remote id"""
    try:
        return User.objects.get(remote_id=remote_id)
    except User.DoesNotExist:
        return None


@register.filter(name="book_title")
def get_title(book: Book, too_short: int = 5) -> Any:
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
def truncatepath(value: Any, arg: str) -> Any:
    """Truncate a path by removing all directories except the first and truncating"""
    path = os.path.normpath(value.name)
    path_list = path.split(os.sep)
    try:
        length = int(arg)
    except ValueError:  # invalid literal for int()
        return path_list[-1]  # Fail silently.
    return f"{path_list[0]}/…{path_list[-1][-length:]}"


@register.simple_tag(takes_context=False)
def get_book_cover_thumbnail(book: Book, size: str = "medium", ext: str = "jpg") -> Any:
    """Returns a book thumbnail at the specified size and extension,
    with fallback if needed"""
    if size == "":
        size = "medium"
    try:
        cover_thumbnail = getattr(book, f"cover_bw_book_{size}_{ext}")
        return cover_thumbnail.url
    except OSError:
        return static("images/no_cover.jpg")


@register.filter(name="possible_series_hint")
def possible_series_hint(seriesbook: SeriesBook) -> str:
    """Returns the hint string for a possible matching series"""
    title = seriesbook.book.title
    path = seriesbook.series.local_path
    author = (
        seriesbook.book.authors.first().name
        if seriesbook.book.authors.first()
        else None
    )

    hint = f'Includes <a href="{path}" target="_blank" rel="nofollow noopener noreferrer">"{title}"</a>'
    if author:
        hint += f" by {author}"

    return mark_safe(hint)


@register.simple_tag(takes_context=False)
def id_to_username(user_id: str, return_empty: bool = False) -> Any:
    """given an arbitrary remote id, return the username"""
    if user_id:
        url = urlparse(user_id)
        domain = url.hostname
        parts = url.path.split("/")
        name = parts[-1]
        value = f"{name}@{domain}"

        return value

    if return_empty:
        return ""

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
        return f"{raw_size / 1024:.2f} KB"
    if raw_size < 1024**3:
        return f"{raw_size / 1024**2:.2f} MB"
    return f"{raw_size / 1024**3:.2f} GB"


@register.simple_tag(takes_context=False)
def max_upload_size() -> int:
    return DATA_UPLOAD_MAX_MEMORY_SIZE


@register.simple_tag(takes_context=False)
def max_upload_size_human() -> str:
    return get_file_size(DATA_UPLOAD_MAX_MEMORY_SIZE)


@register.filter(name="get_user_permission")
def get_user_permission_group(user: User) -> Group | str:
    """given a user, return their permission group"""

    return user.groups.first() or "User"


@register.filter(name="has_perm")
def check_user_has_permission(user: User, perm_name: str) -> bool:
    """does the given user have a specific permission?"""
    return user.has_perm(f"bookwyrm.{perm_name}")


@register.filter(name="is_instance_admin")
def is_instance_admin(localname: str) -> bool:
    """Returns a boolean indicating whether the user is the instance admin account"""
    return localname == INSTANCE_ACTOR_USERNAME


@register.filter(name="dedupe_fields")
def get_dupe_match_field(original: Any, dupe: Any) -> List[str]:
    """Identify which field is matching for a dedupe"""
    return [f.verbose_name for f in original.get_shared_fields(dupe)]
