""" Lets try NOT to sell viagra """
from functools import reduce
import operator

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from bookwyrm.tasks import app, LOW
from .base_model import BookWyrmModel
from .user import User


class AdminModel(BookWyrmModel):
    """Overrides the permissions methods"""

    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True

    def raise_not_editable(self, viewer):
        if viewer.has_perm("bookwyrm.moderate_user"):
            return
        raise PermissionDenied()


class EmailBlocklist(AdminModel):
    """blocked email addresses"""

    domain = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)

    @property
    def users(self):
        """find the users associated with this address"""
        return User.objects.filter(email__endswith=f"@{self.domain}")


class IPBlocklist(AdminModel):
    """blocked ip addresses"""

    address = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)


class AutoMod(AdminModel):
    """rules to automatically flag suspicious activity"""

    string_match = models.CharField(max_length=200, unique=True)
    flag_users = models.BooleanField(default=True)
    flag_statuses = models.BooleanField(default=True)
    created_by = models.ForeignKey("User", on_delete=models.PROTECT)


@app.task(queue=LOW, ignore_result=True)
def automod_task():
    """Create reports"""
    if not AutoMod.objects.exists():
        return
    reporter = AutoMod.objects.first().created_by
    reports = automod_users(reporter) + automod_statuses(reporter)
    if not reports:
        return

    admins = User.admins()
    notification_model = apps.get_model("bookwyrm", "Notification", require_ready=True)
    with transaction.atomic():
        for admin in admins:
            notification, _ = notification_model.objects.get_or_create(
                user=admin, notification_type=notification_model.REPORT, read=False
            )
            notification.related_reports.set(reports)


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
