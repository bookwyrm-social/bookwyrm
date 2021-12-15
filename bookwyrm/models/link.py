""" outlink data """
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from . import fields


class Link(ActivitypubMixin, BookWyrmModel):
    """a link to a website"""

    url = fields.URLField(max_length=255)
    name = fields.CharField(max_length=255)

    def save(self, *args, **kwargs):
        """create a link"""
        # this is never broadcast, the owning model broadcasts an update
        if "broadcast" in kwargs:
            del kwargs["broadcast"]
        return super().save(*args, **kwargs)


class FileLink(Link):
    """a link to a file"""

    filetype = fields.CharField(max_length=5)
