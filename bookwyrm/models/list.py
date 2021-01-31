''' make a list of books!! '''
from django.db import models

from bookwyrm import activitypub
from .base_model import ActivitypubMixin, BookWyrmModel
from .base_model import OrderedCollectionMixin
from . import fields


CurationType = models.TextChoices('Curation', [
    'closed',
    'open',
    'moderated',
])

class List(OrderedCollectionMixin, BookWyrmModel):
    ''' a list of books '''
    name = fields.CharField(max_length=100)
    user = fields.ForeignKey(
        'User', on_delete=models.PROTECT, activitypub_field='owner')
    description = fields.TextField(blank=True, null=True)
    privacy = fields.CharField(
        max_length=255,
        default='public',
        choices=fields.PrivacyLevels.choices
    )
    curation = fields.CharField(
        max_length=255,
        default='closed',
        choices=CurationType.choices
    )
    books = models.ManyToManyField(
        'Edition',
        symmetrical=False,
        through='ListItem',
        through_fields=('book_list', 'book'),
    )
    @property
    def collection_queryset(self):
        ''' list of books for this shelf, overrides OrderedCollectionMixin  '''
        return self.books.all().order_by('listitem')


class ListItem(ActivitypubMixin, BookWyrmModel):
    ''' ok '''
    book = fields.ForeignKey(
        'Edition', on_delete=models.PROTECT, activitypub_field='object')
    book_list = fields.ForeignKey(
        'List', on_delete=models.CASCADE, activitypub_field='target')
    added_by = fields.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        activitypub_field='actor'
    )
    notes = fields.TextField(blank=True, null=True)
    approved = models.BooleanField(default=True)
    order = fields.IntegerField(blank=True, null=True)
    endorsement = models.ManyToManyField('User', related_name='endorsers')

    activity_serializer = activitypub.AddBook

    def to_add_activity(self, user):
        ''' AP for shelving a book'''
        return activitypub.Add(
            id='%s#add' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.book_list.remote_id,
        ).serialize()

    def to_remove_activity(self, user):
        ''' AP for un-shelving a book'''
        return activitypub.Remove(
            id='%s#remove' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.book_list.to_activity()
        ).serialize()

    class Meta:
        ''' an opinionated constraint! you can't put a book on a list twice '''
        unique_together = ('book', 'book_list')
        ordering = ('-created_date',)
