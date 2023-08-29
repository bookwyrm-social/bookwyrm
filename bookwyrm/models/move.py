""" move an object including migrating a user account """
from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import ActivityMixin
from .base_model import BookWyrmModel
from . import fields
from .status import Status


class Move(ActivityMixin, BookWyrmModel):
    """migrating an activitypub user account"""

    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )

    # TODO: can we just use the abstract class here?
    activitypub_object = fields.ForeignKey(
        "BookWyrmModel", on_delete=models.PROTECT,
        activitypub_field="object",
        blank=True,
        null=True
    )

    target = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )

    origin = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )

    activity_serializer = activitypub.Move

    # pylint: disable=unused-argument
    @classmethod
    def ignore_activity(cls, activity, allow_external_connections=True):
        """don't bother with incoming moves of unknown objects"""
        # TODO how do we check this for any conceivable object?
        pass

    def save(self, *args, **kwargs):
        """update user active time"""
        self.user.update_active_date()
        super().save(*args, **kwargs)

    # Ok what else? We can trigger a notification for followers of a user who sends a `Move` for themselves
    # What about when a book is merged (i.e. moved from one id into another)? We could use that to send out a message
    # to other Bookwyrm instances to update their remote_id for the book, but ...how do we trigger any action?