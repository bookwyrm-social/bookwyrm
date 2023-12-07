""" additional formatting of dates """
from django import template
from django.template import defaultfilters
from django.contrib.humanize.templatetags.humanize import naturalday

from bookwyrm.utils.partial_date import PartialDate

register = template.Library()


@register.filter(expects_localtime=True)
def naturalday_partial(date, arg=None):
    """chooses appropriate precision if date is a PartialDate object

    If arg is a Django-defined format such as "DATE_FORMAT", it will be adjusted
    so that the precision of the PartialDate object is honored.
    """
    django_formats = ("DATE_FORMAT", "SHORT_DATE_FORMAT", "YEAR_MONTH_FORMAT")
    if not isinstance(date, PartialDate):
        return defaultfilters.date(date, arg)
    if arg is None:
        arg = "DATE_FORMAT"
    if date.has_day:
        fmt = arg
    elif date.has_month:
        # there is no SHORT_YEAR_MONTH_FORMAT, so we ignore SHORT_DATE_FORMAT :(
        fmt = "YEAR_MONTH_FORMAT" if arg == "DATE_FORMAT" else arg
    else:
        fmt = "Y" if arg in django_formats else arg
    return naturalday(date, fmt)
