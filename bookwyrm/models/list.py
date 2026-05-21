"""make a list of books!!"""

from typing import Optional, Iterable
import uuid

from django.apps import apps
from django.contrib.postgres.indexes import Index
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


class AbstractList(OrderedCollectionMixin, BookWyrmModel):
    """Abstract model for regular lists and suggestion lists"""

    embed_key = models.UUIDField(unique=True, null=True, editable=False)
    activity_serializer = activitypub.BookList
    privacy = fields.PrivacyField()
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="owner"
    )

    def save(self, *args, update_fields: Optional[Iterable[str]] = None, **kwargs):
        """on save, update embed_key and avoid clash with existing code"""
        if not self.embed_key:
            self.embed_key = uuid.uuid4()
            update_fields = add_update_fields(update_fields, "embed_key")

        super().save(*args, update_fields=update_fields, **kwargs)

    @property
    def collection_queryset(self):
        raise NotImplementedError

    class Meta:
        """default sorting"""

        ordering = ("-updated_date",)
        abstract = True


class SuggestionList(AbstractList):
    """a list of user-provided suggested things to read next"""

    works = models.ManyToManyField(
        "Work",
        symmetrical=False,
        through="SuggestionListItem",
        through_fields=("book_list", "work"),
    )

    suggests_for = fields.OneToOneField(
        "Work",
        on_delete=models.PROTECT,
        activitypub_field="book",
        related_name="suggestion_list",
        unique=True,
    )
    activity_serializer = activitypub.SuggestionList

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.works.order_by("suggestionlistitem")

    @property
    def editions(self):
        default_editions = [w.default_edition.id for w in self.works.all()]
        edition_model = apps.get_model("bookwyrm", "Edition")
        return edition_model.objects.filter(id__in=default_editions)

    def save(self, *args, **kwargs):
        """on save, update embed_key and avoid clash with existing code"""
        self.user = activitypub.get_representative()
        self.privacy = "public"

        super().save(*args, **kwargs)

    def raise_not_editable(self, viewer):
        """anyone can create a suggestion list, no one can edit"""
        return

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return f"{BASE_URL}/book/{self.suggests_for.id}/suggestions"

    @property
    def name(self):
        """The name comes from the book title if it's a suggestion list"""
        return _("Suggestions for %(title)s") % {"title": self.suggests_for.title}

    @property
    def description(self):
        """The description comes from the book title if it's a suggestion list"""
        return _(
            "This is the list of suggestions for <a href='%(url)s'>%(title)s</a>"
        ) % {
            "title": self.suggests_for.title,
            "url": self.suggests_for.local_path,
        }


class List(AbstractList):
    """a list of books"""

    editions = models.ManyToManyField(
        "Edition",
        symmetrical=False,
        through="ListItem",
        through_fields=("book_list", "edition"),
    )
    name = fields.CharField(max_length=100)
    description = fields.TextField(blank=True, null=True, activitypub_field="summary")
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

    class Meta:
        """default sorting"""

        indexes = [Index(fields=["privacy", "-updated_date"])]

    @property
    def works(self):
        work_model = apps.get_model("bookwyrm", "Work")
        return work_model.objects.filter(editions__in=self.editions.all()).distinct()

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.editions.filter(listitem__approved=True).order_by("listitem")

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return f"{BASE_URL}/list/{self.id}"

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


class AbstractListItem(CollectionItemMixin, BookWyrmModel):
    """Abstract class for list items for all types of lists"""

    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )
    notes = fields.HtmlField(blank=True, null=True, max_length=300)
    endorsement = models.ManyToManyField("User", related_name="endorsers")

    activity_serializer = activitypub.ListItem
    collection_field = "book_list"

    def endorse(self, user):
        """another user supports this suggestion"""
        # you can't endorse your own contribution, silly
        if user == self.user:
            return
        self.endorsement.add(user)

    def unendorse(self, user):
        """the user rescinds support this suggestion"""
        if user == self.user:
            return
        self.endorsement.remove(user)

    def raise_not_deletable(self, viewer):
        """the associated user OR the list owner can delete"""
        if self.book_list.user == viewer:
            return
        super().raise_not_deletable(viewer)

    class Meta:
        """A book may only be placed into a list once,
        and each order in the list may be used only once"""

        ordering = ("-created_date",)
        abstract = True


class ListItem(AbstractListItem):
    """ok"""

    edition = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="book"
    )

    book_list = models.ForeignKey("List", on_delete=models.CASCADE)
    approved = models.BooleanField(default=True)
    order = fields.IntegerField()

    @property
    def work(self):
        return self.edition.parent_work

    @property
    def privacy(self):
        """inherit the privacy of the list, or direct if pending"""
        collection_field = getattr(self, self.collection_field)
        if self.approved:
            return collection_field.privacy
        return "direct"

    def raise_not_deletable(self, viewer):
        """the associated user OR the list owner can delete"""
        # group members can delete items in group lists
        is_group_member = GroupMember.objects.filter(
            group=self.book_list.group, user=viewer
        ).exists()
        if is_group_member:
            return
        super().raise_not_deletable(viewer)

    def save(self, *args, **kwargs):
        """Update the list's date"""
        super().save(*args, **kwargs)
        # tick the updated date on the parent list
        self.book_list.updated_date = timezone.now()
        self.book_list.save(broadcast=False, update_fields=["updated_date"])

    class Meta:
        """A book may only be placed into a list once,
        and each order in the list may be used only once"""

        unique_together = (("edition", "book_list"), ("order", "book_list"))


class SuggestionListItem(AbstractListItem):
    """items on a suggestion list"""

    work = fields.ForeignKey("Work", on_delete=models.PROTECT, activitypub_field="book")
    book_list = models.ForeignKey("SuggestionList", on_delete=models.CASCADE)
    endorsement = models.ManyToManyField("User", related_name="suggestion_endorsers")
    activity_serializer = activitypub.SuggestionListItem

    @property
    def edition(self):
        return self.work.default_edition

    class Meta:
        """A book may only be placed into a list once,
        and each order in the list may be used only once"""

        unique_together = ("work", "book_list")
