"""Instance statistics dashboard for federation and Readwise metrics"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from csp.decorators import csp_update

from bookwyrm import models
from bookwyrm.connectors.connector_backoff import ConnectorBackoff


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class InstanceStats(View):
    """Extended instance statistics with federation and Readwise metrics"""

    @csp_update(
        SCRIPT_SRC="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
    )
    def get(self, request):
        """Display instance statistics"""
        now = timezone.now()
        interval = int(request.GET.get("days", 7))

        data = {
            **get_federation_stats(),
            **get_readwise_stats(),
            **get_connector_stats(),
            **get_activity_stats(now, interval),
            "interval": interval,
        }

        return TemplateResponse(request, "settings/instance_stats.html", data)


def get_federation_stats():
    """Get federation-related statistics"""
    servers = models.FederatedServer.objects

    # Server counts by status
    federated_count = servers.filter(status="federated").count()
    blocked_count = servers.filter(status="blocked").count()

    # Software breakdown for federated servers
    software_breakdown = (
        servers.filter(status="federated")
        .exclude(application_type__isnull=True)
        .exclude(application_type="")
        .values("application_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Remote users count
    remote_users = models.User.objects.filter(local=False).count()

    # Users from federated vs blocked servers
    users_from_federated = models.User.objects.filter(
        local=False,
        federated_server__status="federated"
    ).count()

    return {
        "federation": {
            "total_servers": federated_count + blocked_count,
            "federated_servers": federated_count,
            "blocked_servers": blocked_count,
            "remote_users": remote_users,
            "users_from_federated": users_from_federated,
            "software_breakdown": list(software_breakdown),
        }
    }


def get_readwise_stats():
    """Get Readwise integration statistics"""
    # Users with Readwise configured
    users_with_token = models.User.objects.filter(
        local=True,
        readwise_token__isnull=False
    ).exclude(readwise_token="").count()

    # Users with auto-export enabled
    users_with_auto_export = models.User.objects.filter(
        local=True,
        readwise_auto_export=True,
        readwise_token__isnull=False
    ).exclude(readwise_token="").count()

    # Exported quotes (quotes with readwise_highlight_id)
    exported_quotes = models.Quotation.objects.filter(
        deleted=False,
        readwise_highlight_id__isnull=False
    ).count()

    # Total quotes available for export
    total_quotes = models.Quotation.objects.filter(
        deleted=False,
        user__local=True
    ).count()

    # Imported highlights
    total_imported = models.ReadwiseSyncedHighlight.objects.count()
    matched_highlights = models.ReadwiseSyncedHighlight.objects.filter(
        quotation__isnull=False
    ).count()
    unmatched_highlights = models.ReadwiseSyncedHighlight.objects.filter(
        quotation__isnull=True
    ).count()

    # Recent sync activity
    recent_syncs = models.ReadwiseSync.objects.filter(
        last_export_at__isnull=False
    ).order_by("-last_export_at")[:5]

    return {
        "readwise": {
            "users_with_token": users_with_token,
            "users_with_auto_export": users_with_auto_export,
            "exported_quotes": exported_quotes,
            "total_quotes": total_quotes,
            "export_percentage": round(
                (exported_quotes / total_quotes * 100) if total_quotes > 0 else 0, 1
            ),
            "total_imported": total_imported,
            "matched_highlights": matched_highlights,
            "unmatched_highlights": unmatched_highlights,
            "match_percentage": round(
                (matched_highlights / total_imported * 100) if total_imported > 0 else 0, 1
            ),
            "recent_syncs": recent_syncs,
        }
    }


def get_connector_stats():
    """Get connector health statistics"""
    connectors = models.Connector.objects.filter(active=True).order_by("priority")
    connector_list = []

    healthy_count = 0
    degraded_count = 0
    unavailable_count = 0

    for connector in connectors:
        # Get real-time stats from cache
        cache_stats = ConnectorBackoff.get_health_stats(connector.identifier)

        connector_data = {
            "identifier": connector.identifier,
            "name": connector.name or connector.identifier,
            "priority": connector.priority,
            "health_status": cache_stats["health_status"],
            "success_rate": cache_stats["success_rate"],
            "success_count": cache_stats["success_count"],
            "failure_count": cache_stats["failure_count"],
            "avg_latency_ms": cache_stats["avg_latency_ms"],
            "in_backoff": cache_stats["in_backoff"],
            "consecutive_failures": cache_stats["consecutive_failures"],
            # Database stats (persistent)
            "db_success_count": connector.success_count,
            "db_failure_count": connector.failure_count,
            "last_success_at": connector.last_success_at,
            "last_failure_at": connector.last_failure_at,
        }
        connector_list.append(connector_data)

        # Count by health status
        if cache_stats["health_status"] == "healthy":
            healthy_count += 1
        elif cache_stats["health_status"] == "degraded":
            degraded_count += 1
        else:
            unavailable_count += 1

    return {
        "connectors": {
            "list": connector_list,
            "total_count": len(connector_list),
            "healthy_count": healthy_count,
            "degraded_count": degraded_count,
            "unavailable_count": unavailable_count,
        }
    }


def get_activity_stats(now, interval_days):
    """Get activity statistics over time for charts"""
    start = now - timedelta(days=interval_days)

    # Daily status counts for chart
    status_by_day = []
    labels = []

    for i in range(interval_days):
        day_start = start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        labels.append(day_start.strftime("%b %d"))

        count = models.Status.objects.filter(
            user__local=True,
            deleted=False,
            created_date__gte=day_start,
            created_date__lt=day_end
        ).count()
        status_by_day.append(count)

    # Daily quote counts for chart
    quotes_by_day = []
    for i in range(interval_days):
        day_start = start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        count = models.Quotation.objects.filter(
            user__local=True,
            deleted=False,
            created_date__gte=day_start,
            created_date__lt=day_end
        ).count()
        quotes_by_day.append(count)

    # Federation activity - new servers discovered
    servers_by_day = []
    for i in range(interval_days):
        day_start = start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        count = models.FederatedServer.objects.filter(
            created_date__gte=day_start,
            created_date__lt=day_end
        ).count()
        servers_by_day.append(count)

    return {
        "activity": {
            "labels": labels,
            "status_by_day": status_by_day,
            "quotes_by_day": quotes_by_day,
            "servers_by_day": servers_by_day,
            "total_statuses_period": sum(status_by_day),
            "total_quotes_period": sum(quotes_by_day),
            "total_servers_period": sum(servers_by_day),
        }
    }
