""" flagged for moderation """
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils.translation import gettext_lazy as _

from bookwyrm.settings import DOMAIN
from .base_model import BookWyrmModel


class Report(BookWyrmModel):
    """reported status or user"""

    reporter = models.ForeignKey(
        "User", related_name="reporter", on_delete=models.PROTECT
    )
    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey("User", on_delete=models.PROTECT, null=True, blank=True)
    status = models.ForeignKey(
        "Status",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    links = models.ManyToManyField("Link", blank=True)
    resolved = models.BooleanField(default=False)

    def raise_not_editable(self, viewer):
        """instead of user being the owner field, it's reporter"""
        if self.reporter == viewer or viewer.has_perm("bookwyrm.moderate_user"):
            return
        raise PermissionDenied()

    def get_remote_id(self):
        return f"https://{DOMAIN}/settings/reports/{self.id}"

    class Meta:
        """set order by default"""

        ordering = ("-created_date",)


ReportCommentTypes = [
    ("comment", _("Comment")),
    ("resolve", _("Resolved report")),
    ("reopen", _("Re-opened report")),
    ("message_reporter", _("Messaged reporter")),
    ("message_offender", _("Messaged reported user")),
    ("user_suspension", _("Suspended user")),
    ("user_deletion", _("Deleted user account")),
    ("block_domain", _("Blocked domain")),
    ("approve_domain", _("Approved domain")),
    ("delete_item", _("Deleted item")),
]
class ReportComment(BookWyrmModel):
    """updates on a report"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    comment_type = models.CharField(
        max_length=20, blank=False, default="comment", choices=ReportCommentTypes
    )
    note = models.TextField()
    report = models.ForeignKey(Report, on_delete=models.PROTECT)

    class Meta:
        """sort comments"""

        ordering = ("-created_date",)
