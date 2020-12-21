''' database schema for info about authors '''
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN

from .base_model import ActivitypubMixin, BookWyrmModel
from . import fields


class Author(ActivitypubMixin, BookWyrmModel):
    ''' basic biographic info '''
    origin_id = models.CharField(max_length=255, null=True)
    openlibrary_key = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True)
    sync = models.BooleanField(default=True)
    last_sync_date = models.DateTimeField(default=timezone.now)
    wikipedia_link = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True)
    # idk probably other keys would be useful here?
    born = fields.DateTimeField(blank=True, null=True)
    died = fields.DateTimeField(blank=True, null=True)
    name = fields.CharField(max_length=255, deduplication_field=True)
    aliases = fields.ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = fields.HtmlField(null=True, blank=True)

    def save(self, *args, **kwargs):
        ''' handle remote vs origin ids '''
        if self.id:
            self.remote_id = self.get_remote_id()
        else:
            self.origin_id = self.remote_id
            self.remote_id = None
        return super().save(*args, **kwargs)

    def get_remote_id(self):
        ''' editions and works both use "book" instead of model_name '''
        return 'https://%s/author/%s' % (DOMAIN, self.id)

    activity_serializer = activitypub.Author
