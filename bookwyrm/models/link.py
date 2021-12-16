""" outlink data """
from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from . import fields


class Link(ActivitypubMixin, BookWyrmModel):
    """a link to a website"""

    url = fields.URLField(max_length=255, activitypub_field="href")
    name = fields.CharField(max_length=255)

    activity_serializer = activitypub.Link
    reverse_unfurl = True

    def save(self, *args, **kwargs):
        """create a link"""
        # this is never broadcast, the owning model broadcasts an update
        if "broadcast" in kwargs:
            del kwargs["broadcast"]
        return super().save(*args, **kwargs)

    def to_activity(self, omit=(), **kwargs):
        """we don't need ALL the fields"""
        return super().to_activity(omit=("@context", "id"), **kwargs)


class FileLink(Link):
    """a link to a file"""

    book = models.ForeignKey(
        "Book", on_delete=models.CASCADE, related_name="file_links", null=True
    )
    filetype = fields.CharField(max_length=5, activitypub_field="mediaType")
