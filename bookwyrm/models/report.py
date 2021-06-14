""" flagged for moderation """
from django.apps import apps
from django.db import models
from django.db.models import F, Q
from .base_model import BookWyrmModel


class Report(BookWyrmModel):
    """reported status or user"""

    reporter = models.ForeignKey(
        "User", related_name="reporter", on_delete=models.PROTECT
    )
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey("User", on_delete=models.PROTECT)
    statuses = models.ManyToManyField("Status", blank=True)
    resolved = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """notify admins when a report is created"""
        super().save(*args, **kwargs)
        user_model = apps.get_model("bookwyrm.User", require_ready=True)
        # moderators and superusers should be notified
        admins = user_model.objects.filter(
            Q(user_permissions__name__in=["moderate_user", "moderate_post"])
            | Q(is_superuser=True)
        ).all()
        notification_model = apps.get_model("bookwyrm.Notification", require_ready=True)
        for admin in admins:
            notification_model.objects.create(
                user=admin,
                related_report=self,
                notification_type="REPORT",
            )

    class Meta:
        """don't let users report themselves"""

        constraints = [
            models.CheckConstraint(check=~Q(reporter=F("user")), name="self_report")
        ]
        ordering = ("-created_date",)


class ReportComment(BookWyrmModel):
    """updates on a report"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    note = models.TextField()
    report = models.ForeignKey(Report, on_delete=models.PROTECT)

    class Meta:
        """sort comments"""

        ordering = ("-created_date",)
