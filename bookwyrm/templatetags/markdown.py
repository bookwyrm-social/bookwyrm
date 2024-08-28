""" template filters """
from typing import Any
from django import template
from bookwyrm.views.status import to_markdown


register = template.Library()


@register.filter(name="to_markdown")
def get_markdown(content: str) -> Any:
    """convert markdown to html"""
    if content:
        return to_markdown(content)
    return None
