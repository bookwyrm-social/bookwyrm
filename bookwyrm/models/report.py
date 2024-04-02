""" flagged for moderation """
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils.translation import gettext_lazy as _

from bookwyrm.settings import DOMAIN
from .base_model import BookWyrmModel


# Report action enums
COMMENT = "comment"
RESOLVE = "resolve"
REOPEN = "reopen"
MESSAGE_REPORTER = "message_reporter"
MESSAGE_OFFENDER = "message_offender"
USER_SUSPENSION = "user_suspension"
USER_UNSUSPENSION = "user_unsuspension"
USER_DELETION = "user_deletion"
USER_PERMS = "user_perms"
BLOCK_DOMAIN = "block_domain"
APPROVE_DOMAIN = "approve_domain"
DELETE_ITEM = "delete_item"


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

    def comment(self, user, note):
        """comment on a report"""
        ReportAction.objects.create(
            action_type=COMMENT, user=user, note=note, report=self
        )

    def resolve(self, user):
        """Mark a report as complete"""
        self.resolved = True
        self.save()
        ReportAction.objects.create(action_type=RESOLVE, user=user, report=self)

    def reopen(self, user):
        """Wait! This report isn't complete after all"""
        self.resolved = False
        self.save()
        ReportAction.objects.create(action_type=REOPEN, user=user, report=self)

    @classmethod
    def record_action(cls, report_id: int, action: str, user):
        """Note that someone did something"""
        if not report_id:
            return
        report = cls.objects.get(id=report_id)
        ReportAction.objects.create(action_type=action, user=user, report=report)

    class Meta:
        """set order by default"""

        ordering = ("-created_date",)


ReportActionTypes = [
    (COMMENT, _("Comment")),
    (RESOLVE, _("Resolved report")),
    (REOPEN, _("Re-opened report")),
    (MESSAGE_REPORTER, _("Messaged reporter")),
    (MESSAGE_OFFENDER, _("Messaged reported user")),
    (USER_SUSPENSION, _("Suspended user")),
    (USER_UNSUSPENSION, _("Un-suspended user")),
    (USER_PERMS, _("Changed user permission level")),
    (USER_DELETION, _("Deleted user account")),
    (BLOCK_DOMAIN, _("Blocked domain")),
    (APPROVE_DOMAIN, _("Approved domain")),
    (DELETE_ITEM, _("Deleted item")),
]


class ReportAction(BookWyrmModel):
    """updates on a report"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    action_type = models.CharField(
        max_length=20, blank=False, default="comment", choices=ReportActionTypes
    )
    note = models.TextField()
    report = models.ForeignKey(Report, on_delete=models.PROTECT)

    class Meta:
        """sort comments"""

        ordering = ("created_date",)
