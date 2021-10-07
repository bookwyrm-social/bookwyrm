""" outlink data """
from .activitypub_mixin import CollectionItemMixin
from .base_model import BookWyrmModel
from . import fields


class Link(CollectionItemMixin, BookWyrmModel):
    """a link to a website"""

    url = fields.CharField(max_length=255)
    name = fields.CharField(max_length=255)


class FileLink(Link):
    """a link to a file"""

    filetype = fields.CharField(max_length=5)
    filetype_description = fields.CharField(max_length=100)
