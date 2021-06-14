""" like/fav/star a status """
from django.apps import apps
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from .activitypub_mixin import ActivityMixin
from .base_model import BookWyrmModel
from . import fields
from .status import Status


class Favorite(ActivityMixin, BookWyrmModel):
    """fav'ing a post"""

    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )
    status = fields.ForeignKey(
        "Status", on_delete=models.PROTECT, activitypub_field="object"
    )

    activity_serializer = activitypub.Like

    @classmethod
    def ignore_activity(cls, activity):
        """don't bother with incoming favs of unknown statuses"""
        return not Status.objects.filter(remote_id=activity.object).exists()

    def save(self, *args, **kwargs):
        """update user active time"""
        self.user.last_active_date = timezone.now()
        self.user.save(broadcast=False)
        super().save(*args, **kwargs)

        if self.status.user.local and self.status.user != self.user:
            notification_model = apps.get_model(
                "bookwyrm.Notification", require_ready=True
            )
            notification_model.objects.create(
                user=self.status.user,
                notification_type="FAVORITE",
                related_user=self.user,
                related_status=self.status,
            )

    def delete(self, *args, **kwargs):
        """delete and delete notifications"""
        # check for notification
        if self.status.user.local:
            notification_model = apps.get_model(
                "bookwyrm.Notification", require_ready=True
            )
            notification = notification_model.objects.filter(
                user=self.status.user,
                related_user=self.user,
                related_status=self.status,
                notification_type="FAVORITE",
            ).first()
            if notification:
                notification.delete()
        super().delete(*args, **kwargs)

    class Meta:
        """can't fav things twice"""

        unique_together = ("user", "status")
