""" responds to various requests to /.well-know """

from dateutil.relativedelta import relativedelta
from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookwyrm import models
from bookwyrm.settings import DOMAIN, VERSION, MEDIA_FULL_URL


@require_GET
def webfinger(request):
    """allow other servers to ask about a user"""
    resource = request.GET.get("resource")
    if not resource or not resource.startswith("acct:"):
        return HttpResponseNotFound()

    username = resource.replace("acct:", "")
    user = get_object_or_404(models.User, username__iexact=username)

    return JsonResponse(
        {
            "subject": f"acct:{user.username}",
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": user.remote_id,
                }
            ],
        }
    )


@require_GET
def nodeinfo_pointer(_):
    """direct servers to nodeinfo"""
    return JsonResponse(
        {
            "links": [
                {
                    "rel": "http://nodeinfo.diaspora.software/ns/schema/2.0",
                    "href": f"https://{DOMAIN}/nodeinfo/2.0",
                }
            ]
        }
    )


@require_GET
def nodeinfo(_):
    """basic info about the server"""
    status_count = models.Status.objects.filter(user__local=True, deleted=False).count()
    user_count = models.User.objects.filter(is_active=True, local=True).count()

    month_ago = timezone.now() - relativedelta(months=1)
    last_month_count = models.User.objects.filter(
        is_active=True, local=True, last_active_date__gt=month_ago
    ).count()

    six_months_ago = timezone.now() - relativedelta(months=6)
    six_month_count = models.User.objects.filter(
        is_active=True, local=True, last_active_date__gt=six_months_ago
    ).count()

    site = models.SiteSettings.get()
    return JsonResponse(
        {
            "version": "2.0",
            "software": {"name": "bookwyrm", "version": VERSION},
            "protocols": ["activitypub"],
            "usage": {
                "users": {
                    "total": user_count,
                    "activeMonth": last_month_count,
                    "activeHalfyear": six_month_count,
                },
                "localPosts": status_count,
            },
            "openRegistrations": site.allow_registration,
        }
    )


@require_GET
def instance_info(_):
    """let's talk about your cool unique instance"""
    user_count = models.User.objects.filter(is_active=True, local=True).count()
    status_count = models.Status.objects.filter(user__local=True, deleted=False).count()

    site = models.SiteSettings.get()
    logo_path = site.logo or "images/logo.png"
    logo = f"{MEDIA_FULL_URL}{logo_path}"
    return JsonResponse(
        {
            "uri": DOMAIN,
            "title": site.name,
            "short_description": site.instance_short_description,
            "description": site.instance_description,
            "version": VERSION,
            "stats": {
                "user_count": user_count,
                "status_count": status_count,
            },
            "thumbnail": logo,
            "languages": ["en"],
            "registrations": site.allow_registration,
            "approval_required": site.allow_registration and site.allow_invite_requests,
            "email": site.admin_email,
        }
    )


@require_GET
def peers(_):
    """list of federated servers this instance connects with"""
    names = models.FederatedServer.objects.filter(status="federated").values_list(
        "server_name", flat=True
    )
    return JsonResponse(list(names), safe=False)


@require_GET
def host_meta(request):
    """meta of the host"""
    return TemplateResponse(request, "host_meta.xml", {"DOMAIN": DOMAIN})


@require_GET
def opensearch(request):
    """Open Search xml spec"""
    site = models.SiteSettings.get()
    logo_path = site.favicon or "images/favicon.png"
    logo = f"{MEDIA_FULL_URL}{logo_path}"
    return TemplateResponse(
        request, "opensearch.xml", {"image": logo, "DOMAIN": DOMAIN}
    )
