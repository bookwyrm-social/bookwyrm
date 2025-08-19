""" tags used on the feed pages """
from typing import Any
from django import template
from bookwyrm.views.feed import get_suggested_books
from bookwyrm import models


register = template.Library()


@register.filter(name="load_subclass")
def load_subclass(status: models.Status) -> models.Status:
    """sometimes you didn't select_subclass"""
    if hasattr(status, "quotation"):
        return status.quotation
    if hasattr(status, "review"):
        return status.review
    if hasattr(status, "comment"):
        return status.comment
    if hasattr(status, "generatednote"):
        return status.generatednote
    return status


@register.simple_tag(takes_context=True)
def suggested_books(context: dict[str, Any]) -> Any:
    """get books for suggested books panel"""
    # this happens here instead of in the view so that the template snippet can
    # be cached in the template
    return get_suggested_books(context["request"].user)
