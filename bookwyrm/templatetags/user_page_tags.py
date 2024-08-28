""" template filters """
from typing import Any, Optional
from django import template
from bookwyrm import models


register = template.Library()


@register.simple_tag(takes_context=True)
def mutuals_count(context: dict[str, Any], user: models.User) -> Optional[int]:
    """how many users that you follow, follow them"""
    viewer = context["request"].user
    if not viewer.is_authenticated:
        return None
    return user.followers.filter(followers=viewer).count()
