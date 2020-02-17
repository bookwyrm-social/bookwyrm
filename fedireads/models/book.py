''' database schema for books and shelves '''
from django.db import models

from fedireads.settings import DOMAIN
from fedireads.utils.fields import JSONField
from fedireads.utils.models import FedireadsModel


class Shelf(FedireadsModel):
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    books = models.ManyToManyField(
        'Book',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('shelf', 'book')
    )

    class Meta:
        unique_together = ('user', 'identifier')


class ShelfBook(FedireadsModel):
    # many to many join table for books and shelves
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )

    class Meta:
        unique_together = ('book', 'shelf')


class Book(FedireadsModel):
    ''' a non-canonical copy of a work (not book) from open library '''
    openlibrary_key = models.CharField(max_length=255, unique=True)
    data = JSONField()
    authors = models.ManyToManyField('Author')
    # TODO: also store cover thumbnail
    cover = models.ImageField(upload_to='covers/', blank=True, null=True)
    shelves = models.ManyToManyField(
        'Shelf',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('book', 'shelf')
    )
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        base_path = 'https://%s' % DOMAIN
        model_name = self.__name__.lower()
        return '%s/%s/%d' % (base_path, model_name, self.openlibrary_key)


class Author(FedireadsModel):
    ''' copy of an author from OL '''
    openlibrary_key = models.CharField(max_length=255)
    data = JSONField()

