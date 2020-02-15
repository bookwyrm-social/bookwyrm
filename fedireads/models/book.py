''' database schema for books and shelves '''
from django.db import models
from fedireads.utils.fields import JSONField


class Shelf(models.Model):
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
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'identifier')


class ShelfBook(models.Model):
    # many to many join table for books and shelves
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('book', 'shelf')


class Book(models.Model):
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
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class Author(models.Model):
    ''' copy of an author from OL '''
    openlibrary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

