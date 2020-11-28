''' puttin' books on shelves '''
import re
from django.db import models

from bookwyrm import activitypub
from .base_model import ActivityMapping, BookWyrmModel
from .base_model import OrderedCollectionMixin, PrivacyLevels


class Shelf(OrderedCollectionMixin, BookWyrmModel):
    ''' a list of books owned by a user '''
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    privacy = models.CharField(
        max_length=255,
        default='public',
        choices=PrivacyLevels.choices
    )
    books = models.ManyToManyField(
        'Edition',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('shelf', 'book')
    )

    def save(self, *args, **kwargs):
        ''' set the identifier '''
        saved = super().save(*args, **kwargs)
        if not self.identifier:
            slug = re.sub(r'[^\w]', '', self.name).lower()
            self.identifier = '%s-%d' % (slug, self.id)
            return super().save(*args, **kwargs)
        return saved

    @property
    def collection_queryset(self):
        ''' list of books for this shelf, overrides OrderedCollectionMixin  '''
        return self.books

    def get_remote_id(self):
        ''' shelf identifier instead of id '''
        base_path = self.user.remote_id
        return '%s/shelf/%s' % (base_path, self.identifier)

    class Meta:
        ''' user/shelf unqiueness '''
        unique_together = ('user', 'identifier')

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('owner', 'user'),
        ActivityMapping('name', 'name'),
    ]


class ShelfBook(BookWyrmModel):
    ''' many to many join table for books and shelves '''
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('actor', 'added_by'),
        ActivityMapping('object', 'book'),
        ActivityMapping('target', 'shelf')
    ]

    activity_serializer = activitypub.AddBook

    def to_add_activity(self, user):
        ''' AP for shelving a book'''
        return activitypub.Add(
            id='%s#add' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.shelf.remote_id,
        ).serialize()

    def to_remove_activity(self, user):
        ''' AP for un-shelving a book'''
        return activitypub.Remove(
            id='%s#remove' % self.remote_id,
            actor=user.remote_id,
            object=self.book.to_activity(),
            target=self.shelf.to_activity()
        ).serialize()


    class Meta:
        ''' an opinionated constraint!
            you can't put a book on shelf twice '''
        unique_together = ('book', 'shelf')
