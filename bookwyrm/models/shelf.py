""" puttin' books on shelves """
import re
from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from . import fields


class Shelf(OrderedCollectionMixin, BookWyrmModel):
    """ a list of books owned by a user """

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
        """ set the identifier """
        super().save(*args, **kwargs)
        if not self.identifier:
            slug = re.sub(r"[^\w]", "", self.name).lower()
            self.identifier = "%s-%d" % (slug, self.id)
            super().save(*args, **kwargs)

    @property
    def collection_queryset(self):
        """ list of books for this shelf, overrides OrderedCollectionMixin  """
        return self.books.all().order_by("shelfbook")

    def get_remote_id(self):
        """ shelf identifier instead of id """
        base_path = self.user.remote_id
        return "%s/shelf/%s" % (base_path, self.identifier)

    class Meta:
        """ user/shelf unqiueness """

        unique_together = ("user", "identifier")


class ShelfBook(CollectionItemMixin, BookWyrmModel):
    """ many to many join table for books and shelves """

    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="object"
    )
    shelf = fields.ForeignKey(
        "Shelf", on_delete=models.PROTECT, activitypub_field="target"
    )
    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )

    activity_serializer = activitypub.Add
    object_field = "book"
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
