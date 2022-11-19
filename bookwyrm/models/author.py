""" database schema for info about authors """
import re
from django.contrib.postgres.indexes import GinIndex
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import models
from stdnum.iso7064 import mod_11_2

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
        max_length=16, blank=True, null=True, deduplication_field=True
    )
    gutenberg_id = fields.CharField(
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
        """clear related template caches"""
        # clear template caches
        if self.id:
            cache_keys = [
                make_template_fragment_key("titleby", [book])
                for book in self.book_set.values_list("id", flat=True)
            ]
            cache.delete_many(cache_keys)

        # normalize isni format
        if self.isni:
            self.isni = re.sub(r"\s", "", self.isni)
            # While we are here we can check if it is an isni
            if self.isni.isdigit() != False:
                if self.isni[-1] != "x" or "X" or self.isni[:-1].isdigit() != False:
                    self.isni = ""
            else:
                length = len(self.isni)
                if length > 16:  # too long
                    self.isni = ""
                elif length == 16:
                    if self.isni[0:4] != "0000":
                        self.isni = ""
                else:
                    if mod_11_2.checksum(self.isni) != 1:
                        self.isni = ""
                    elif length < 16:
                        multi = 16 - length
                        self.isni = ("0" * multi) + self.isni
                        if mod_11_2.checksum(self.isni) != 1:
                            self.isni = ""
                    else:
                        self.isni = ""

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

    def get_remote_id(self):
        """editions and works both use "book" instead of model_name"""
        return f"https://{DOMAIN}/author/{self.id}"

    activity_serializer = activitypub.Author

    class Meta:
        """sets up postgres GIN index field"""

        indexes = (GinIndex(fields=["search_vector"]),)
