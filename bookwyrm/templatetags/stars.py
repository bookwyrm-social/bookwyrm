""" template filters """
from django import template


register = template.Library()


@register.filter(name="half_star")
def get_half_star(value):
    """one of those things that's weirdly hard with templates"""
    return f"{value}.5"
