''' models for storing different kinds of Activities '''
import urllib.parse

from django.db import models

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from .base_model import OrderedCollectionMixin, BookWyrmModel


class Tag(OrderedCollectionMixin, BookWyrmModel):
    ''' freeform tags for books '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)

    @classmethod
    def book_queryset(cls, identifier):
        ''' county of books associated with this tag '''
        return cls.objects.filter(identifier=identifier)

    @property
    def collection_queryset(self):
        ''' books associated with this tag '''
        return self.book_queryset(self.identifier)

    def get_remote_id(self):
        ''' tag should use identifier not id in remote_id '''
        base_path = 'https://%s' % DOMAIN
        return '%s/tag/%s' % (base_path, self.identifier)

    def to_add_activity(self, user):
        ''' AP for shelving a book'''
        return activitypub.Add(
            id='%s#add' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.remote_id,
        ).serialize()

    def to_remove_activity(self, user):
        ''' AP for un-shelving a book'''
        return activitypub.Remove(
            id='%s#remove' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.to_activity(),
        ).serialize()

    def save(self, *args, **kwargs):
        ''' create a url-safe lookup key for the tag '''
        if not self.id:
            # add identifiers to new tags
            self.identifier = urllib.parse.quote_plus(self.name)
        super().save(*args, **kwargs)

    class Meta:
        ''' unqiueness constraint '''
        unique_together = ('user', 'book', 'name')
