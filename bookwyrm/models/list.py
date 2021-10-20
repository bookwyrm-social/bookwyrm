""" make a list of books!! """
from django.apps import apps
from django.db import models
from django.db.models import Q
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN

from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from .group import GroupMember
from . import fields

CurationType = models.TextChoices(
    "Curation",
    ["closed", "open", "curated", "group"],
)


class List(OrderedCollectionMixin, BookWyrmModel):
    """a list of books"""

    name = fields.CharField(max_length=100)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="owner"
    )
    description = fields.TextField(blank=True, null=True, activitypub_field="summary")
    privacy = fields.PrivacyField()
    curation = fields.CharField(
        max_length=255, default="closed", choices=CurationType.choices
    )
    group = models.ForeignKey(
        "Group",
        on_delete=models.SET_NULL,
        default=None,
        blank=True,
        null=True,
    )
    books = models.ManyToManyField(
        "Edition",
        symmetrical=False,
        through="ListItem",
        through_fields=("book_list", "book"),
    )
    activity_serializer = activitypub.BookList

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return f"https://{DOMAIN}/list/{self.id}"

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.books.filter(listitem__approved=True).order_by("listitem")

    class Meta:
        """default sorting"""

        ordering = ("-updated_date",)

    def raise_not_editable(self, viewer):
        """the associated user OR the list owner can edit"""
        if self.user == viewer:
            return
        # group members can edit items in group lists
        is_group_member = GroupMember.objects.filter(
            group=self.group, user=viewer
        ).exists()
        if is_group_member:
            return
        super().raise_not_editable(viewer)

    @classmethod
    def followers_filter(cls, queryset, viewer):
        """Override filter for "followers" privacy level to allow non-following
        group members to see the existence of group lists"""

        return queryset.exclude(
            ~Q(  # user isn't following or group member
                Q(user__followers=viewer)
                | Q(user=viewer)
                | Q(group__memberships__user=viewer)
            ),
            privacy="followers",  # and the status (of the list) is followers only
        )

    @classmethod
    def direct_filter(cls, queryset, viewer):
        """Override filter for "direct" privacy level to allow
        group members to see the existence of group lists"""

        return queryset.exclude(
            ~Q(  # user not self and not in the group if this is a group list
                Q(user=viewer) | Q(group__memberships__user=viewer)
            ),
            privacy="direct",
        )

    @classmethod
    def remove_from_group(cls, owner, user):
        """remove a list from a group"""

        cls.objects.filter(group__user=owner, user=user).all().update(
            group=None, curation="closed"
        )


class ListItem(CollectionItemMixin, BookWyrmModel):
    """ok"""

    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="book"
    )
    book_list = models.ForeignKey("List", on_delete=models.CASCADE)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )
    notes = fields.TextField(blank=True, null=True)
    approved = models.BooleanField(default=True)
    order = fields.IntegerField()
    endorsement = models.ManyToManyField("User", related_name="endorsers")

    activity_serializer = activitypub.ListItem
    collection_field = "book_list"

    def save(self, *args, **kwargs):
        """create a notification too"""
        created = not bool(self.id)
        super().save(*args, **kwargs)
        # tick the updated date on the parent list
        self.book_list.updated_date = timezone.now()
        self.book_list.save(broadcast=False)

        list_owner = self.book_list.user
        model = apps.get_model("bookwyrm.Notification", require_ready=True)
        # create a notification if somoene ELSE added to a local user's list
        if created and list_owner.local and list_owner != self.user:
            model.objects.create(
                user=list_owner,
                related_user=self.user,
                related_list_item=self,
                notification_type="ADD",
            )

        if self.book_list.group:
            for membership in self.book_list.group.memberships.all():
                if membership.user != self.user:
                    model.objects.create(
                        user=membership.user,
                        related_user=self.user,
                        related_list_item=self,
                        notification_type="ADD",
                    )

    def raise_not_deletable(self, viewer):
        """the associated user OR the list owner can delete"""
        if self.book_list.user == viewer:
            return
        # group members can delete items in group lists
        is_group_member = GroupMember.objects.filter(
            group=self.book_list.group, user=viewer
        ).exists()
        if is_group_member:
            return
        super().raise_not_deletable(viewer)

    class Meta:
        """A book may only be placed into a list once,
        and each order in the list may be used only once"""

        unique_together = (("book", "book_list"), ("order", "book_list"))
        ordering = ("-created_date",)
