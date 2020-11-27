''' database schema for info about authors '''
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.utils.fields import ArrayField

from .base_model import ActivitypubMixin, ActivityMapping, BookWyrmModel


class Author(ActivitypubMixin, BookWyrmModel):
    ''' basic biographic info '''
    origin_id = models.CharField(max_length=255, null=True)
    ''' copy of an author from OL '''
    openlibrary_key = models.CharField(max_length=255, blank=True, null=True)
    sync = models.BooleanField(default=True)
    last_sync_date = models.DateTimeField(default=timezone.now)
    wikipedia_link = models.CharField(max_length=255, blank=True, null=True)
    # idk probably other keys would be useful here?
    born = models.DateTimeField(blank=True, null=True)
    died = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    aliases = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = models.TextField(null=True, blank=True)

    @property
    def display_name(self):
        ''' Helper to return a displayable name'''
        if self.name:
            return self.name
        # don't want to return a spurious space if all of these are None
        if self.first_name and self.last_name:
            return self.first_name + ' ' + self.last_name
        return self.last_name or self.first_name

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('name', 'name'),
        ActivityMapping('born', 'born'),
        ActivityMapping('died', 'died'),
        ActivityMapping('aliases', 'aliases'),
        ActivityMapping('bio', 'bio'),
        ActivityMapping('openlibraryKey', 'openlibrary_key'),
        ActivityMapping('wikipediaLink', 'wikipedia_link'),
    ]
    activity_serializer = activitypub.Author
