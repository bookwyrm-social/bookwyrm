""" instance overview """
from datetime import timedelta
import re

from dateutil.parser import parse
from packaging import version

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from csp.decorators import csp_update

from bookwyrm import models, settings
from bookwyrm.connectors.abstract_connector import get_data
from bookwyrm.utils import regex


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class Dashboard(View):
    """admin overview"""

    @csp_update(
        SCRIPT_SRC="https://cdn.jsdelivr.net/npm/chart.js@3.5.1/dist/chart.min.js"
    )
    def get(self, request):
        """list of users"""
        data = get_charts_and_stats(request)

        # Make sure email looks properly configured
        email_config_error = re.findall(
            r"[\s\@]", settings.EMAIL_SENDER_DOMAIN
        ) or not re.match(regex.DOMAIN, settings.EMAIL_SENDER_DOMAIN)

        data["email_config_error"] = email_config_error
        # pylint: disable=line-too-long
        data[
            "email_sender"
        ] = f"{settings.EMAIL_SENDER_NAME}@{settings.EMAIL_SENDER_DOMAIN}"

        site = models.SiteSettings.objects.get()
        # pylint: disable=protected-access
        data["missing_conduct"] = (
            not site.code_of_conduct
            or site.code_of_conduct
            == site._meta.get_field("code_of_conduct").get_default()
        )
        data["missing_privacy"] = (
            not site.privacy_policy
            or site.privacy_policy
            == site._meta.get_field("privacy_policy").get_default()
        )

        # check version

        try:
            release = get_data(settings.RELEASE_API, timeout=3)
            available_version = release.get("tag_name", None)
            if available_version and version.parse(available_version) > version.parse(
                settings.VERSION
            ):
                data["current_version"] = settings.VERSION
                data["available_version"] = available_version
        except:  # pylint: disable= bare-except
            pass

        return TemplateResponse(request, "settings/dashboard/dashboard.html", data)


def get_charts_and_stats(request):
    """Defines the dashboard charts"""
    interval = int(request.GET.get("days", 1))
    now = timezone.now()
    start = request.GET.get("start")
    if start:
        start = timezone.make_aware(parse(start))
    else:
        start = now - timedelta(days=6 * interval)

    end = request.GET.get("end")
    end = timezone.make_aware(parse(end)) if end else now
    start = start.replace(hour=0, minute=0, second=0)

    user_queryset = models.User.objects.filter(local=True)
    user_chart = Chart(
        queryset=user_queryset,
        queries={
            "total": lambda q, s, e: q.filter(
                Q(is_active=True) | Q(deactivation_date__gt=e),
                created_date__lte=e,
            ).count(),
            "active": lambda q, s, e: q.filter(
                Q(is_active=True) | Q(deactivation_date__gt=e),
                created_date__lte=e,
            )
            .filter(
                last_active_date__gt=e - timedelta(days=31),
            )
            .count(),
        },
    )

    status_queryset = models.Status.objects.filter(user__local=True, deleted=False)
    status_chart = Chart(
        queryset=status_queryset,
        queries={
            "total": lambda q, s, e: q.filter(
                created_date__gt=s,
                created_date__lte=e,
            ).count()
        },
    )

    register_chart = Chart(
        queryset=user_queryset,
        queries={
            "total": lambda q, s, e: q.filter(
                created_date__gt=s,
                created_date__lte=e,
            ).count()
        },
    )

    works_chart = Chart(
        queryset=models.Work.objects,
        queries={
            "total": lambda q, s, e: q.filter(
                created_date__gt=s,
                created_date__lte=e,
            ).count()
        },
    )
    return {
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
        "pending_domains": models.LinkDomain.objects.filter(status="pending").count(),
        "invite_requests": models.InviteRequest.objects.filter(
            ignored=False, invite__isnull=True
        ).count(),
        "user_stats": user_chart.get_chart(start, end, interval),
        "status_stats": status_chart.get_chart(start, end, interval),
        "register_stats": register_chart.get_chart(start, end, interval),
        "works_stats": works_chart.get_chart(start, end, interval),
    }


class Chart:
    """Data for a chart"""

    def __init__(self, queryset, queries: dict):
        self.queryset = queryset
        self.queries = queries

    def get_chart(self, start, end, interval):
        """load the data for the chart given a time scale and interval"""
        interval_start = start
        interval_end = interval_start + timedelta(days=interval)

        chart = {k: [] for k in self.queries.keys()}
        chart["labels"] = []
        while interval_start <= end:
            for (name, query) in self.queries.items():
                chart[name].append(query(self.queryset, interval_start, interval_end))
            chart["labels"].append(interval_start.strftime("%b %d"))

            interval_start = interval_end
            interval_end += timedelta(days=interval)

        return chart
