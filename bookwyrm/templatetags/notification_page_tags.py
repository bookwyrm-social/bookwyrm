""" tags used on the feed pages """
from typing import Optional
from django import template
from bookwyrm import models
from bookwyrm.templatetags.feed_page_tags import load_subclass


register = template.Library()


@register.simple_tag(takes_context=False)
def related_status(notification: models.Notification) -> Optional[models.Status]:
    """for notifications"""
    if not notification.related_status:
        return None
    return load_subclass(notification.related_status)


@register.simple_tag(takes_context=False)
def get_related_users(notification: models.Notification) -> list[models.User]:
    """Who actually was it who liked your post"""
    return list(reversed(list(notification.related_users.distinct())))[:10]
