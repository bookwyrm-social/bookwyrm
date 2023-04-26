""" database schema for info about authors """
import re
from django.contrib.postgres.indexes import GinIndex
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
    gutenberg_id = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    isfdb = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )

    website = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    # idk probably other keys would be useful here?
    born = fields.DateTimeField(blank=True, null=True)
    died = fields.DateTimeField(blank=True, null=True)
    name = fields.CharField(max_length=255)
    aliases = fields.ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = fields.HtmlField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """normalize isni format"""
        if self.isni:
            self.isni = re.sub(r"\s", "", self.isni)

        return super().save(*args, **kwargs)

    @property
    def isni_link(self):
        """generate the url from the isni id"""
        clean_isni = re.sub(r"\s", "", self.isni)
        return f"https://isni.org/isni/{clean_isni}"

    @property
    def openlibrary_link(self):
        """generate the url from the openlibrary id"""
        return f"https://openlibrary.org/authors/{self.openlibrary_key}"

    @property
    def isfdb_link(self):
        """generate the url from the isni id"""
        return f"https://www.isfdb.org/cgi-bin/ea.cgi?{self.isfdb}"

    def get_remote_id(self):
        """editions and works both use "book" instead of model_name"""
        return f"https://{DOMAIN}/author/{self.id}"

    activity_serializer = activitypub.Author

    class Meta:
        """sets up postgres GIN index field"""

        indexes = (GinIndex(fields=["search_vector"]),)
