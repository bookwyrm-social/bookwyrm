''' database schema for the whole dang thing '''
from django.db import models
from model_utils.managers import InheritanceManager
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from Crypto import Random
from Crypto.PublicKey import RSA
import re

from fedireads.settings import DOMAIN, OL_URL

class Shelf(models.Model):
    activitypub_id = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    shelf_type = models.CharField(default='custom', max_length=100)
    books = models.ManyToManyField(
        'Book',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('shelf', 'book')
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'name')

    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = '%s_%s' % (
                self.user.localname,
                re.sub(r'\W', '-', self.name).lower()
            )
        if not self.activitypub_id:
            self.activitypub_id = 'https://%s/shelf/%s' % \
                    (DOMAIN, self.identifier)
        super().save(*args, **kwargs)


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
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('book', 'shelf')


class Book(models.Model):
    ''' a non-canonical copy of a work (not book) from open library '''
    activitypub_id = models.CharField(max_length=255)
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

    def save(self, *args, **kwargs):
        self.activitypub_id = '%s%s' % (OL_URL, self.openlibrary_key)
        super().save(*args, **kwargs)


class Author(models.Model):
    openlibrary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

