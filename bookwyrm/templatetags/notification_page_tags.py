""" tags used on the feed pages """
from django import template
from bookwyrm.templatetags.feed_page_tags import load_subclass


register = template.Library()


@register.simple_tag(takes_context=False)
def related_status(notification):
    """for notifications"""
    if not notification.related_status:
        return None
    return load_subclass(notification.related_status)
