""" defines relationships between users """
from django.apps import apps
from django.db import models, transaction, IntegrityError
from django.db.models import Q

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin, ActivityMixin
from .activitypub_mixin import generate_activity
from .base_model import BookWyrmModel
from . import fields


class UserRelationship(BookWyrmModel):
    """many-to-many through table for followers"""

    user_subject = fields.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="%(class)s_user_subject",
        activitypub_field="actor",
    )
    user_object = fields.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="%(class)s_user_object",
        activitypub_field="object",
    )

    @property
    def privacy(self):
        """all relationships are handled directly with the participants"""
        return "direct"

    @property
    def recipients(self):
        """the remote user needs to recieve direct broadcasts"""
        return [u for u in [self.user_subject, self.user_object] if not u.local]

    class Meta:
        """relationships should be unique"""

        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["user_subject", "user_object"], name="%(class)s_unique"
            ),
            models.CheckConstraint(
                check=~models.Q(user_subject=models.F("user_object")),
                name="%(class)s_no_self",
            ),
        ]

    def get_remote_id(self):
        """use shelf identifier in remote_id"""
        base_path = self.user_subject.remote_id
        return "%s#follows/%d" % (base_path, self.id)


class UserFollows(ActivityMixin, UserRelationship):
    """Following a user"""

    status = "follows"

    def to_activity(self):  # pylint: disable=arguments-differ
        """overrides default to manually set serializer"""
        return activitypub.Follow(**generate_activity(self))

    def save(self, *args, **kwargs):
        """really really don't let a user follow someone who blocked them"""
        # blocking in either direction is a no-go
        if UserBlocks.objects.filter(
            Q(
                user_subject=self.user_subject,
                user_object=self.user_object,
            )
            | Q(
                user_subject=self.user_object,
                user_object=self.user_subject,
            )
        ).exists():
            raise IntegrityError()
        # don't broadcast this type of relationship -- accepts and requests
        # are handled by the UserFollowRequest model
        super().save(*args, broadcast=False, **kwargs)

    @classmethod
    def from_request(cls, follow_request):
        """converts a follow request into a follow relationship"""
        return cls.objects.create(
            user_subject=follow_request.user_subject,
            user_object=follow_request.user_object,
            remote_id=follow_request.remote_id,
        )


class UserFollowRequest(ActivitypubMixin, UserRelationship):
    """following a user requires manual or automatic confirmation"""

    status = "follow_request"
    activity_serializer = activitypub.Follow

    def save(self, *args, broadcast=True, **kwargs):
        """make sure the follow or block relationship doesn't already exist"""
        # if there's a request for a follow that already exists, accept it
        # without changing the local database state
        if UserFollows.objects.filter(
            user_subject=self.user_subject,
            user_object=self.user_object,
        ).exists():
            self.accept(broadcast_only=True)
            return

        # blocking in either direction is a no-go
        if UserBlocks.objects.filter(
            Q(
                user_subject=self.user_subject,
                user_object=self.user_object,
            )
            | Q(
                user_subject=self.user_object,
                user_object=self.user_subject,
            )
        ).exists():
            raise IntegrityError()
        super().save(*args, **kwargs)

        if broadcast and self.user_subject.local and not self.user_object.local:
            self.broadcast(self.to_activity(), self.user_subject)

        if self.user_object.local:
            manually_approves = self.user_object.manually_approves_followers
            if not manually_approves:
                self.accept()

            model = apps.get_model("bookwyrm.Notification", require_ready=True)
            notification_type = "FOLLOW_REQUEST" if manually_approves else "FOLLOW"
            model.objects.create(
                user=self.user_object,
                related_user=self.user_subject,
                notification_type=notification_type,
            )

    def get_accept_reject_id(self, status):
        """get id for sending an accept or reject of a local user"""

        base_path = self.user_object.remote_id
        return "%s#%s/%d" % (base_path, status, self.id or 0)

    def accept(self, broadcast_only=False):
        """turn this request into the real deal"""
        user = self.user_object
        if not self.user_subject.local:
            activity = activitypub.Accept(
                id=self.get_accept_reject_id(status="accepts"),
                actor=self.user_object.remote_id,
                object=self.to_activity(),
            ).serialize()
            self.broadcast(activity, user)
        if broadcast_only:
            return

        with transaction.atomic():
            UserFollows.from_request(self)
            self.delete()

    def reject(self):
        """generate a Reject for this follow request"""
        if self.user_object.local:
            activity = activitypub.Reject(
                id=self.get_accept_reject_id(status="rejects"),
                actor=self.user_object.remote_id,
                object=self.to_activity(),
            ).serialize()
            self.broadcast(activity, self.user_object)

        self.delete()


class UserBlocks(ActivityMixin, UserRelationship):
    """prevent another user from following you and seeing your posts"""

    status = "blocks"
    activity_serializer = activitypub.Block

    def save(self, *args, **kwargs):
        """remove follow or follow request rels after a block is created"""
        super().save(*args, **kwargs)

        UserFollows.objects.filter(
            Q(user_subject=self.user_subject, user_object=self.user_object)
            | Q(user_subject=self.user_object, user_object=self.user_subject)
        ).delete()
        UserFollowRequest.objects.filter(
            Q(user_subject=self.user_subject, user_object=self.user_object)
            | Q(user_subject=self.user_object, user_object=self.user_subject)
        ).delete()
