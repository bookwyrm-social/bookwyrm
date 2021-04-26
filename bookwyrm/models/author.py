""" database schema for info about authors """
from django.db import models

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN

from .book import BookDataModel
from . import fields


class Author(BookDataModel):
    """basic biographic info"""

    wikipedia_link = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    isni = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    viaf_id = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    gutenberg_id = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    # idk probably other keys would be useful here?
    born = fields.DateTimeField(blank=True, null=True)
    died = fields.DateTimeField(blank=True, null=True)
    name = fields.CharField(max_length=255, deduplication_field=True)
    aliases = fields.ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = fields.HtmlField(null=True, blank=True)

    def get_remote_id(self):
        """editions and works both use "book" instead of model_name"""
        return "https://%s/author/%s" % (DOMAIN, self.id)

    activity_serializer = activitypub.Author
