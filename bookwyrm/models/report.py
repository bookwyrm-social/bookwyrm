""" flagged for moderation """
from django.db import models
from bookwyrm.settings import DOMAIN
from .base_model import BookWyrmModel


class Report(BookWyrmModel):
    """reported status or user"""

    reporter = models.ForeignKey(
        "User", related_name="reporter", on_delete=models.PROTECT
    )
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey("User", on_delete=models.PROTECT)
    status = models.ForeignKey(
        "Status",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    links = models.ManyToManyField("Link", blank=True)
    resolved = models.BooleanField(default=False)

    def get_remote_id(self):
        return f"https://{DOMAIN}/settings/reports/{self.id}"

    class Meta:
        """set order by default"""

        ordering = ("-created_date",)


class ReportComment(BookWyrmModel):
    """updates on a report"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    note = models.TextField()
    report = models.ForeignKey(Report, on_delete=models.PROTECT)

    class Meta:
        """sort comments"""

        ordering = ("-created_date",)
