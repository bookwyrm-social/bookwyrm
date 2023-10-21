""" formatting of SealedDate instances """
from django import template
from django.template import defaultfilters
from django.contrib.humanize.templatetags.humanize import naturalday

from bookwyrm.utils.sealed_date import SealedDate

register = template.Library()


@register.filter(expects_localtime=True, is_safe=False)
def naturalday_partial(date):
    if not isinstance(date, SealedDate):
        return defaultfilters.date(date)
    if date.has_day:
        fmt = "DATE_FORMAT"
    elif date.has_month:
        fmt = "YEAR_MONTH_FORMAT"
    else:
        fmt = "Y"
    return naturalday(date, fmt)
