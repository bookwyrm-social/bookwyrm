""" instance overview """
from datetime import timedelta
from dateutil.parser import parse

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class Dashboard(View):
    """admin overview"""

    def get(self, request):
        """list of users"""
        interval = int(request.GET.get("days", 1))
        now = timezone.now()

        user_queryset = models.User.objects.filter(local=True)
        user_stats = {"labels": [], "total": [], "active": []}

        status_queryset = models.Status.objects.filter(user__local=True, deleted=False)
        status_stats = {"labels": [], "total": []}

        start = request.GET.get("start")
        if start:
            start = timezone.make_aware(parse(start))
        else:
            start = now - timedelta(days=6 * interval)

        end = request.GET.get("end")
        end = timezone.make_aware(parse(end)) if end else now
        start = start.replace(hour=0, minute=0, second=0)

        interval_start = start
        interval_end = interval_start + timedelta(days=interval)
        while interval_start <= end:
            print(interval_start, interval_end)
            interval_queryset = user_queryset.filter(
                Q(is_active=True) | Q(deactivation_date__gt=interval_end),
                created_date__lte=interval_end,
            )
            user_stats["total"].append(interval_queryset.filter().count())
            user_stats["active"].append(
                interval_queryset.filter(
                    last_active_date__gt=interval_end - timedelta(days=31),
                ).count()
            )
            user_stats["labels"].append(interval_start.strftime("%b %d"))

            status_stats["total"].append(
                status_queryset.filter(
                    created_date__gt=interval_start,
                    created_date__lte=interval_end,
                ).count()
            )
            status_stats["labels"].append(interval_start.strftime("%b %d"))
            interval_start = interval_end
            interval_end += timedelta(days=interval)

        data = {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "interval": interval,
            "users": user_queryset.filter(is_active=True).count(),
            "active_users": user_queryset.filter(
                is_active=True, last_active_date__gte=now - timedelta(days=31)
            ).count(),
            "statuses": status_queryset.count(),
            "works": models.Work.objects.count(),
            "reports": models.Report.objects.filter(resolved=False).count(),
            "invite_requests": models.InviteRequest.objects.filter(
                ignored=False, invite_sent=False
            ).count(),
            "user_stats": user_stats,
            "status_stats": status_stats,
        }
        return TemplateResponse(request, "settings/dashboard/dashboard.html", data)
