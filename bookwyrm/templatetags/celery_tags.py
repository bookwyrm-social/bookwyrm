""" template filters for really common utilities """
import datetime
from django import template


register = template.Library()


@register.filter(name="uptime")
def uptime(seconds):
    """Seconds uptime to a readable format"""
    return str(datetime.timedelta(seconds=seconds))


@register.filter(name="runtime")
def runtime(timestamp):
    """How long has it been?"""
    return datetime.datetime.now() - datetime.datetime.fromtimestamp(timestamp)


@register.filter(name="shortname")
def shortname(name):
    """removes bookwyrm.celery..."""
    return ".".join(name.split(".")[-2:])
