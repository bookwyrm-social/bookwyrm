""" do book related things with other users """
from django.db import models, IntegrityError, transaction
from django.db.models import Q
from bookwyrm.settings import DOMAIN
from .base_model import BookWyrmModel
from . import fields
from .relationship import UserBlocks


class Group(BookWyrmModel):
    """A group of users"""

    name = fields.CharField(max_length=100)
    user = fields.ForeignKey("User", on_delete=models.CASCADE)
    description = fields.TextField(blank=True, null=True)
    privacy = fields.PrivacyField()

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return f"https://{DOMAIN}/group/{self.id}"

    @classmethod
    def followers_filter(cls, queryset, viewer):
        """Override filter for "followers" privacy level to allow non-following
        group members to see the existence of group-curated lists"""

        return queryset.exclude(
            ~Q(  # user is not a group member
                Q(user__followers=viewer) | Q(user=viewer) | Q(memberships__user=viewer)
            ),
            privacy="followers",  # and the status of the group is followers only
        )

    @classmethod
    def direct_filter(cls, queryset, viewer):
        """Override filter for "direct" privacy level to allow group members
        to see the existence of groups and group lists"""

        return queryset.exclude(~Q(memberships__user=viewer), privacy="direct")


class GroupMember(models.Model):
    """Users who are members of a group"""

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    group = models.ForeignKey(
        "Group", on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="memberships"
    )

    class Meta:
        """Users can only have one membership per group"""

        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_membership")
        ]

    def save(self, *args, **kwargs):
        """don't let a user invite someone who blocked them"""
        # blocking in either direction is a no-go
        if UserBlocks.objects.filter(
            Q(
                user_subject=self.group.user,
                user_object=self.user,
            )
            | Q(
                user_subject=self.user,
                user_object=self.group.user,
            )
        ).exists():
            raise IntegrityError()
        # accepts and requests are handled by the GroupMemberInvitation model
        super().save(*args, **kwargs)

    @classmethod
    def from_request(cls, join_request):
        """converts a join request into a member relationship"""

        # remove the invite
        join_request.delete()

        # make a group member
        return cls.objects.create(
            user=join_request.user,
            group=join_request.group,
        )

    @classmethod
    def remove(cls, owner, user):
        """remove a user from a group"""

        memberships = cls.objects.filter(group__user=owner, user=user).all()
        for member in memberships:
            member.delete()


class GroupMemberInvitation(models.Model):
    """adding a user to a group requires manual confirmation"""

    created_date = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(
        "Group", on_delete=models.CASCADE, related_name="user_invitations"
    )
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="group_invitations"
    )

    class Meta:
        """Users can only have one outstanding invitation per group"""

        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_invitation")
        ]

    def save(self, *args, **kwargs):
        """make sure the membership doesn't already exist"""
        # if there's an invitation for a membership that already exists, accept it
        # without changing the local database state
        if GroupMember.objects.filter(user=self.user, group=self.group).exists():
            self.accept()
            return

        # blocking in either direction is a no-go
        if UserBlocks.objects.filter(
            Q(
                user_subject=self.group.user,
                user_object=self.user,
            )
            | Q(
                user_subject=self.user,
                user_object=self.group.user,
            )
        ).exists():
            raise IntegrityError()

        # make an invitation
        super().save(*args, **kwargs)

    @transaction.atomic
    def accept(self):
        """turn this request into the real deal"""
        # pylint: disable-next=import-outside-toplevel
        from .notification import Notification, NotificationType  # circular dependency

        GroupMember.from_request(self)

        # tell the group owner
        Notification.notify(
            self.group.user,
            self.user,
            related_group=self.group,
            notification_type=NotificationType.ACCEPT,
        )

        # let the other members know about it
        for membership in self.group.memberships.all():
            member = membership.user
            if member not in (self.user, self.group.user):
                Notification.notify(
                    member,
                    self.user,
                    related_group=self.group,
                    notification_type=NotificationType.JOIN,
                )

    def reject(self):
        """generate a Reject for this membership request"""
        self.delete()
