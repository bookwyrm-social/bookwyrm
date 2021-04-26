""" media that is posted in the app """
from django.db import models

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from . import fields


class Attachment(ActivitypubMixin, BookWyrmModel):
    """an image (or, in the future, video etc) associated with a status"""

    status = models.ForeignKey(
        "Status", on_delete=models.CASCADE, related_name="attachments", null=True
    )
    reverse_unfurl = True

    class Meta:
        """one day we'll have other types of attachments besides images"""

        abstract = True


class Image(Attachment):
    """an image attachment"""

    image = fields.ImageField(
        upload_to="status/",
        null=True,
        blank=True,
        activitypub_field="url",
        alt_field="caption",
    )
    caption = fields.TextField(null=True, blank=True, activitypub_field="name")

    activity_serializer = activitypub.Document
