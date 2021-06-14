""" puttin' books on shelves """
import re
from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from . import fields


class Shelf(OrderedCollectionMixin, BookWyrmModel):
    """a list of books owned by a user"""

    TO_READ = "to-read"
    READING = "reading"
    READ_FINISHED = "read"

    READ_STATUS_IDENTIFIERS = (TO_READ, READING, READ_FINISHED)

    name = fields.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="owner"
    )
    editable = models.BooleanField(default=True)
    privacy = fields.PrivacyField()
    books = models.ManyToManyField(
        "Edition",
        symmetrical=False,
        through="ShelfBook",
        through_fields=("shelf", "book"),
    )

    activity_serializer = activitypub.Shelf

    def save(self, *args, **kwargs):
        """set the identifier"""
        super().save(*args, **kwargs)
        if not self.identifier:
            self.identifier = self.get_identifier()
            super().save(*args, **kwargs, broadcast=False)

    def get_identifier(self):
        """custom-shelf-123 for the url"""
        slug = re.sub(r"[^\w]", "", self.name).lower()
        return "{:s}-{:d}".format(slug, self.id)

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.books.order_by("shelfbook")

    def get_remote_id(self):
        """shelf identifier instead of id"""
        base_path = self.user.remote_id
        identifier = self.identifier or self.get_identifier()
        return "%s/books/%s" % (base_path, identifier)

    class Meta:
        """user/shelf unqiueness"""

        unique_together = ("user", "identifier")


class ShelfBook(CollectionItemMixin, BookWyrmModel):
    """many to many join table for books and shelves"""

    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="book"
    )
    shelf = models.ForeignKey("Shelf", on_delete=models.PROTECT)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )

    activity_serializer = activitypub.ShelfItem
    collection_field = "shelf"

    def save(self, *args, **kwargs):
        if not self.user:
            self.user = self.shelf.user
        super().save(*args, **kwargs)

    class Meta:
        """an opinionated constraint!
        you can't put a book on shelf twice"""

        unique_together = ("book", "shelf")
        ordering = ("-created_date",)
