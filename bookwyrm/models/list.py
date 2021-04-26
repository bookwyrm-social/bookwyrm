""" make a list of books!! """
from django.apps import apps
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from . import fields


CurationType = models.TextChoices(
    "Curation",
    [
        "closed",
        "open",
        "curated",
    ],
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
    books = models.ManyToManyField(
        "Edition",
        symmetrical=False,
        through="ListItem",
        through_fields=("book_list", "book"),
    )
    activity_serializer = activitypub.BookList

    def get_remote_id(self):
        """don't want the user to be in there in this case"""
        return "https://%s/list/%d" % (DOMAIN, self.id)

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.books.filter(listitem__approved=True).order_by("listitem")

    class Meta:
        """default sorting"""

        ordering = ("-updated_date",)


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
        # create a notification if somoene ELSE added to a local user's list
        if created and list_owner.local and list_owner != self.user:
            model = apps.get_model("bookwyrm.Notification", require_ready=True)
            model.objects.create(
                user=list_owner,
                related_user=self.user,
                related_list_item=self,
                notification_type="ADD",
            )

    class Meta:
        # A book may only be placed into a list once, and each order in the list may be used only
        # once
        unique_together = (("book", "book_list"), ("order", "book_list"))
        ordering = ("-created_date",)
