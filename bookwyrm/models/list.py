""" make a list of books!! """
from typing import Optional, Iterable
import uuid

from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookwyrm import activitypub
from bookwyrm.settings import BASE_URL
from bookwyrm.utils.db import add_update_fields

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
    embed_key = models.UUIDField(unique=True, null=True, editable=False)
    activity_serializer = activitypub.BookList
    suggests_for = fields.OneToOneField(
        "Edition",
        on_delete=models.PROTECT,
        activitypub_field="book",
        related_name="suggestion_list",
        default=None,
        null=True,
    )

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return f"{BASE_URL}/list/{self.id}"

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.books.filter(listitem__approved=True).order_by("listitem")

    @property
    def get_name(self):
        """The name comes from the book title if it's a suggestion list"""
        if self.suggests_for:
            return _("Suggestions for %(title)s") % {"title": self.suggests_for.title}

        return self.name

    @property
    def get_description(self):
        """The description comes from the book title if it's a suggestion list"""
        if self.suggests_for:
            return _(
                "This is the list of suggestions for <a href='%(url)s'>%(title)s</a>"
            ) % {
                "title": self.suggests_for.title,
                "url": self.suggests_for.local_path,
            }

        return self.description

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

    def raise_not_submittable(self, viewer):
        """can the user submit a book to the list?"""
        # if you can't view the list you can't submit to it
        self.raise_visible_to_user(viewer)

        # all good if you're the owner or the list is open
        if self.user == viewer or self.curation in ["open", "curated"]:
            return
        if self.curation == "group":
            is_group_member = GroupMember.objects.filter(
                group=self.group, user=viewer
            ).exists()
            if is_group_member:
                return
        raise PermissionDenied()

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

    def save(self, *args, update_fields: Optional[Iterable[str]] = None, **kwargs):
        """on save, update embed_key and avoid clash with existing code"""
        if not self.embed_key:
            self.embed_key = uuid.uuid4()
            update_fields = add_update_fields(update_fields, "embed_key")

        super().save(*args, update_fields=update_fields, **kwargs)


class ListItem(CollectionItemMixin, BookWyrmModel):
    """ok"""

    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="book"
    )
    book_list = models.ForeignKey("List", on_delete=models.CASCADE)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )
    notes = fields.HtmlField(blank=True, null=True, max_length=300)
    approved = models.BooleanField(default=True)
    order = fields.IntegerField()
    endorsement = models.ManyToManyField("User", related_name="endorsers")

    activity_serializer = activitypub.ListItem
    collection_field = "book_list"

    def save(self, *args, **kwargs):
        """Update the list's date"""
        super().save(*args, **kwargs)
        # tick the updated date on the parent list
        self.book_list.updated_date = timezone.now()
        self.book_list.save(broadcast=False, update_fields=["updated_date"])

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
