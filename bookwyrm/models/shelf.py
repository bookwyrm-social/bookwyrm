""" puttin' books on shelves """
import re
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from bookwyrm.tasks import LOW
from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from . import fields


class Shelf(OrderedCollectionMixin, BookWyrmModel):
    """a list of books owned by a user"""

    TO_READ = "to-read"
    READING = "reading"
    READ_FINISHED = "read"
    STOPPED_READING = "stopped-reading"

    READ_STATUS_IDENTIFIERS = (TO_READ, READING, READ_FINISHED, STOPPED_READING)

    name = fields.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True, max_length=500)
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

    def save(self, *args, priority=LOW, **kwargs):
        """set the identifier"""
        super().save(*args, priority=priority, **kwargs)
        if not self.identifier:
            self.identifier = self.get_identifier()
            super().save(*args, **kwargs, broadcast=False)

    def get_identifier(self):
        """custom-shelf-123 for the url"""
        slug = re.sub(r"[^\w]", "", self.name).lower()
        return f"{slug}-{self.id}"

    @property
    def collection_queryset(self):
        """list of books for this shelf, overrides OrderedCollectionMixin"""
        return self.books.order_by("shelfbook")

    @property
    def deletable(self):
        """can the shelf be safely deleted?"""
        return self.editable and not self.shelfbook_set.exists()

    def get_remote_id(self):
        """shelf identifier instead of id"""
        base_path = self.user.remote_id
        identifier = self.identifier or self.get_identifier()
        return f"{base_path}/books/{identifier}"

    @property
    def local_path(self):
        """No slugs"""
        return self.get_remote_id().replace(f"https://{DOMAIN}", "")

    def raise_not_deletable(self, viewer):
        """don't let anyone delete a default shelf"""
        super().raise_not_deletable(viewer)
        if not self.deletable:
            raise PermissionDenied()

    class Meta:
        """user/shelf unqiueness"""

        unique_together = ("user", "identifier")


class ShelfBook(CollectionItemMixin, BookWyrmModel):
    """many to many join table for books and shelves"""

    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="book"
    )
    shelf = models.ForeignKey("Shelf", on_delete=models.PROTECT)
    shelved_date = models.DateTimeField(default=timezone.now)
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )

    activity_serializer = activitypub.ShelfItem
    collection_field = "shelf"

    def save(self, *args, priority=LOW, **kwargs):
        if not self.user:
            self.user = self.shelf.user
        if self.id and self.user.local:
            # remove all caches related to all editions of this book
            cache.delete_many(
                [
                    f"book-on-shelf-{book.id}-{self.shelf_id}"
                    for book in self.book.parent_work.editions.all()
                ]
            )
        super().save(*args, priority=priority, **kwargs)

    def delete(self, *args, **kwargs):
        if self.id and self.user.local:
            cache.delete_many(
                [
                    f"book-on-shelf-{book}-{self.shelf_id}"
                    for book in self.book.parent_work.editions.values_list(
                        "id", flat=True
                    )
                ]
            )
        super().delete(*args, **kwargs)

    class Meta:
        """an opinionated constraint!
        you can't put a book on shelf twice"""

        unique_together = ("book", "shelf")
        ordering = ("-shelved_date", "-created_date", "-updated_date")
