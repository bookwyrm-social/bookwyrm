""" flagged for moderation """
from django.db import models
from .base_model import BookWyrmModel


class Report(BookWyrmModel):
    """ reported status or user """

    reporter = models.ForeignKey(
        "User", related_name="reporter", on_delete=models.PROTECT
    )
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey("User", on_delete=models.PROTECT)
    statuses = models.ManyToManyField("Status")
    resolved = models.BooleanField(default=False)


class ReportComment(BookWyrmModel):
    """ updates on a report """

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    note = models.TextField()
    report = models.ForeignKey(Report, on_delete=models.PROTECT)
