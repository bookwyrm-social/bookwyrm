"""like/fav/star a status"""

from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import ActivityMixin, ActivityObject
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
    def ignore_activity(
        cls, activity: ActivityObject, allow_external_connections: bool = True
    ) -> bool:
        """don't bother with incoming favs of unknown statuses"""
        return not Status.objects.filter(remote_id=activity.object).exists()

    def save(self, *args, **kwargs) -> None:
        """update user active time"""
        self.user.update_active_date()
        super().save(*args, **kwargs)

    class Meta:
        """can't fav things twice"""

        unique_together = ("user", "status")
