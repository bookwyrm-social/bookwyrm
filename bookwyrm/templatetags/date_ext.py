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
    if not isinstance(date, PartialDate) or date.has_day:
        return naturalday(date, arg)
    if not arg or arg == "DATE_FORMAT":
        arg = "YEAR_MONTH_FORMAT" if date.has_month else "Y"
    elif not date.has_month and arg in ("SHORT_DATE_FORMAT", "YEAR_MONTH_FORMAT"):
        arg = "Y"
    return defaultfilters.date(date, arg)
