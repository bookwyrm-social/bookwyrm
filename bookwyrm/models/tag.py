""" models for storing different kinds of Activities """
import urllib.parse

from django.apps import apps
from django.db import models

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from .activitypub_mixin import CollectionItemMixin, OrderedCollectionMixin
from .base_model import BookWyrmModel
from . import fields


class Tag(OrderedCollectionMixin, BookWyrmModel):
    """ freeform tags for books """

    name = fields.CharField(max_length=100, unique=True)
    identifier = models.CharField(max_length=100)

    @property
    def books(self):
        """ count of books associated with this tag """
        edition_model = apps.get_model("bookwyrm.Edition", require_ready=True)
        return (
            edition_model.objects.filter(usertag__tag__identifier=self.identifier)
            .order_by("-created_date")
            .distinct()
        )

    collection_queryset = books

    def get_remote_id(self):
        """ tag should use identifier not id in remote_id """
        base_path = "https://%s" % DOMAIN
        return "%s/tag/%s" % (base_path, self.identifier)

    def save(self, *args, **kwargs):
        """ create a url-safe lookup key for the tag """
        if not self.id:
            # add identifiers to new tags
            self.identifier = urllib.parse.quote_plus(self.name)
        super().save(*args, **kwargs)


class UserTag(CollectionItemMixin, BookWyrmModel):
    """ an instance of a tag on a book by a user """

    user = fields.ForeignKey(
        "User", on_delete=models.PROTECT, activitypub_field="actor"
    )
    book = fields.ForeignKey(
        "Edition", on_delete=models.PROTECT, activitypub_field="object"
    )
    tag = fields.ForeignKey("Tag", on_delete=models.PROTECT, activitypub_field="target")

    activity_serializer = activitypub.Add
    object_field = "book"
    collection_field = "tag"

    class Meta:
        """ unqiueness constraint """

        unique_together = ("user", "book", "tag")
