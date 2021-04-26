""" alert a user to activity """
from django.db import models
from .base_model import BookWyrmModel


NotificationType = models.TextChoices(
    "NotificationType",
    "FAVORITE REPLY MENTION TAG FOLLOW FOLLOW_REQUEST BOOST IMPORT ADD REPORT",
)


class Notification(BookWyrmModel):
    """you've been tagged, liked, followed, etc"""

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    related_book = models.ForeignKey("Edition", on_delete=models.CASCADE, null=True)
    related_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, null=True, related_name="related_user"
    )
    related_status = models.ForeignKey("Status", on_delete=models.CASCADE, null=True)
    related_import = models.ForeignKey("ImportJob", on_delete=models.CASCADE, null=True)
    related_list_item = models.ForeignKey(
        "ListItem", on_delete=models.CASCADE, null=True
    )
    related_report = models.ForeignKey("Report", on_delete=models.CASCADE, null=True)
    read = models.BooleanField(default=False)
    notification_type = models.CharField(
        max_length=255, choices=NotificationType.choices
    )

    def save(self, *args, **kwargs):
        """save, but don't make dupes"""
        # there's probably a better way to do this
        if self.__class__.objects.filter(
            user=self.user,
            related_book=self.related_book,
            related_user=self.related_user,
            related_status=self.related_status,
            related_import=self.related_import,
            related_list_item=self.related_list_item,
            related_report=self.related_report,
            notification_type=self.notification_type,
        ).exists():
            return
        super().save(*args, **kwargs)

    class Meta:
        """checks if notifcation is in enum list for valid types"""

        constraints = [
            models.CheckConstraint(
                check=models.Q(notification_type__in=NotificationType.values),
                name="notification_type_valid",
            )
        ]
