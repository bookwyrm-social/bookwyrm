""" non-interactive pages """
from dateutil.relativedelta import relativedelta
from django.http import Http404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookwyrm import models, settings


@require_GET
def about(request):
    """more information about the instance"""
    six_months_ago = timezone.now() - relativedelta(months=6)
    six_month_count = models.User.objects.filter(
        is_active=True, local=True, last_active_date__gt=six_months_ago
    ).count()
    data = {
        "active_users": six_month_count,
        "status_count": models.Status.objects.filter(
            user__local=True, deleted=False
        ).count(),
        "admins": models.User.admins(),
        "version": settings.VERSION,
    }

    return TemplateResponse(request, "about/about.html", data)


@require_GET
def conduct(request):
    """more information about the instance"""
    return TemplateResponse(request, "about/conduct.html")


@require_GET
def privacy(request):
    """more information about the instance"""
    return TemplateResponse(request, "about/privacy.html")


@require_GET
def impressum(request):
    """more information about the instance"""
    site = models.SiteSettings.objects.get()
    if not site.show_impressum:
        raise Http404()
    return TemplateResponse(request, "about/impressum.html")
