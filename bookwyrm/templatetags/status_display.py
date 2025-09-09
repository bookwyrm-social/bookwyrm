""" template filters """
import datetime
from typing import Any, Optional
from dateutil.relativedelta import relativedelta
from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime, naturalday
from django.template.loader import select_template
from django.utils import timezone
from bookwyrm import models
from bookwyrm.templatetags.utilities import get_user_identifier


register = template.Library()


@register.filter(name="mentions")
def get_mentions(status: models.Status, user: models.User) -> str:
    """people to @ in a reply: the parent and all mentions"""
    mentions = set([status.user] + list(status.mention_users.all()))
    return (
        " ".join("@" + get_user_identifier(m) for m in mentions if not m == user) + " "
    )


@register.filter(name="replies")
def get_replies(status: models.Status) -> Any:
    """get all direct replies to a status"""
    # TODO: this limit could cause problems
    return models.Status.objects.filter(
        reply_parent=status,
        deleted=False,
    ).select_subclasses()[:10]


@register.filter(name="parent")
def get_parent(status: models.Status) -> Any:
    """get the reply parent for a status"""
    if status.reply_parent_id:
        return (
            models.Status.objects.filter(id=status.reply_parent_id)
            .select_subclasses()
            .first()
        )
    return None


@register.filter(name="boosted_status")
def get_boosted(boost: models.Boost) -> Any:
    """load a boosted status. have to do this or it won't get foreign keys"""
    return (
        models.Status.objects.select_subclasses()
        .select_related("user", "reply_parent")
        .prefetch_related("mention_books", "mention_users")
        .get(id=boost.boosted_status.id)
    )


@register.filter(name="published_date")
def get_published_date(date: datetime.datetime) -> str | None:
    """less verbose combo of humanize filters"""
    if not date:
        return ""
    now = timezone.now()
    delta = relativedelta(now, date)
    if delta.years:
        return naturalday(date)
    if delta.days or delta.months:
        return naturalday(date, settings.MONTH_DAY_FORMAT)
    return naturaltime(date)


@register.simple_tag()
def get_header_template(status: models.Status) -> Any:
    """get the path for the status template"""
    if isinstance(status, models.Boost):
        status = status.boosted_status
    try:
        header_type = status.reading_status.replace("-", "_")
        if not header_type:
            raise AttributeError()
    except AttributeError:
        header_type = status.status_type.lower()
    filename = f"snippets/status/headers/{header_type}.html"
    header_template = select_template([filename, "snippets/status/headers/note.html"])
    return header_template.render({"status": status})


@register.simple_tag(takes_context=False)
def load_book(status: models.Status) -> Optional[models.Book]:
    """how many users that you follow, follow them"""
    return status.book if hasattr(status, "book") else status.mention_books.first()
