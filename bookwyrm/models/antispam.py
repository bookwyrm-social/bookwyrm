""" Lets try NOT to sell viagra """
from functools import reduce
import operator

from django.apps import apps
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from bookwyrm.tasks import app
from .user import User


class EmailBlocklist(models.Model):
    """blocked email addresses"""

    created_date = models.DateTimeField(auto_now_add=True)
    domain = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)

    @property
    def users(self):
        """find the users associated with this address"""
        return User.objects.filter(email__endswith=f"@{self.domain}")


class IPBlocklist(models.Model):
    """blocked ip addresses"""

    created_date = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)


class AutoMod(models.Model):
    """rules to automatically flag suspicious activity"""

    string_match = models.CharField(max_length=200, unique=True)
    flag_users = models.BooleanField(default=True)
    flag_statuses = models.BooleanField(default=True)
    created_by = models.ForeignKey("User", on_delete=models.PROTECT)


@app.task(queue="low_priority")
def automod_task():
    """Create reports"""
    if not AutoMod.objects.exists():
        return
    reporter = AutoMod.objects.first().created_by
    reports = automod_users(reporter) + automod_statuses(reporter)
    if reports:
        admins = User.objects.filter(
            models.Q(user_permissions__name__in=["moderate_user", "moderate_post"])
            | models.Q(is_superuser=True)
        ).all()
        notification_model = apps.get_model(
            "bookwyrm", "Notification", require_ready=True
        )
        for admin in admins:
            notification_model.objects.bulk_create(
                [
                    notification_model(
                        user=admin,
                        related_report=r,
                        notification_type="REPORT",
                    )
                    for r in reports
                ]
            )


def automod_users(reporter):
    """check users for moderation flags"""
    user_rules = AutoMod.objects.filter(flag_users=True).values_list(
        "string_match", flat=True
    )
    if not user_rules:
        return []

    filters = []
    for field in ["username", "summary", "name"]:
        filters += [{f"{field}__icontains": r} for r in user_rules]
    users = User.objects.filter(
        reduce(operator.or_, (Q(**f) for f in filters)),
        is_active=True,
        local=True,
        report__isnull=True,  # don't flag users that already have reports
    ).distinct()

    report_model = apps.get_model("bookwyrm", "Report", require_ready=True)

    return report_model.objects.bulk_create(
        [
            report_model(
                reporter=reporter,
                note=_("Automatically generated report"),
                user=u,
            )
            for u in users
        ]
    )


def automod_statuses(reporter):
    """check statues for moderation flags"""
    status_rules = AutoMod.objects.filter(flag_statuses=True).values_list(
        "string_match", flat=True
    )

    if not status_rules:
        return []

    filters = []
    for field in ["content", "content_warning", "quotation__quote", "review__name"]:
        filters += [{f"{field}__icontains": r} for r in status_rules]

    status_model = apps.get_model("bookwyrm", "Status", require_ready=True)
    statuses = status_model.objects.filter(
        reduce(operator.or_, (Q(**f) for f in filters)),
        deleted=False,
        local=True,
        report__isnull=True,  # don't flag statuses that already have reports
    ).distinct()

    report_model = apps.get_model("bookwyrm", "Report", require_ready=True)
    return report_model.objects.bulk_create(
        [
            report_model(
                reporter=reporter,
                note=_("Automatically generated report"),
                user=s.user,
                status=s,
            )
            for s in statuses
        ]
    )
