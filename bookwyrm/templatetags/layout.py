""" template filters used for creating the layout"""
from django import template, utils


register = template.Library()


@register.simple_tag(takes_context=False)
def get_lang():
    """get current language, strip to the first two letters"""
    language = utils.translation.get_language()
    return language[0 : language.find("-")]
