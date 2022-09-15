""" template filters for really common utilities """
import datetime
from django import template


register = template.Library()


@register.filter(name="uptime")
def uptime(seconds):
    """Seconds uptime to a readable format"""
    return str(datetime.timedelta(seconds=seconds))


@register.filter(name="datestamp")
def get_date(timestamp):
    """Go from a string timestamp to a date object"""
    return datetime.datetime.fromtimestamp(timestamp)


@register.filter(name="shortname")
def shortname(name):
    """removes bookwyrm.celery..."""
    return ".".join(name.split(".")[-2:])
