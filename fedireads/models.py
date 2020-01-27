''' database schema for the whole dang thing '''
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from Crypto.PublicKey import RSA
from Crypto import Random
from fedireads.settings import DOMAIN, OL_URL
import re

class User(AbstractUser):
    ''' a user who wants to read books '''
    full_username = models.CharField(max_length=255, blank=True, null=True, unique=True)
    private_key = models.TextField(blank=True, null=True)
    public_key = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    actor = models.CharField(max_length=255)
    local = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    followers = models.ManyToManyField('self', symmetrical=False)

    def save(self, *args, **kwargs):
        # give a new user keys
        if not self.private_key:
            random_generator = Random.new().read
            key = RSA.generate(1024, random_generator)
            self.private_key = key.export_key().decode('utf8')
            self.public_key = key.publickey().export_key().decode('utf8')

        if self.local and not self.actor:
            self.actor = 'https://%s/api/u/%s' % (DOMAIN, self.username)
        if self.local and not self.full_username:
            self.full_username = '%s@%s' % (self.username, DOMAIN)

        super().save(*args, **kwargs)


@receiver(models.signals.post_save, sender=User)
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' create shelves for new users '''
    # TODO: how are remote users handled? what if they aren't readers?
    if not created:
        return
    shelves = [{
        'name': 'To Read',
        'type': 'to-read',
    }, {
        'name': 'Currently Reading',
        'type': 'reading',
    }, {
        'name': 'Read',
        'type': 'read',
    }]

    for shelf in shelves:
        Shelf(
            name=shelf['name'],
            shelf_type=shelf['type'],
            user=instance,
            editable=False
        ).save()


class Message(models.Model):
    ''' any kind of user post, incl. reviews, replies, and status updates '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    content = JSONField(max_length=5000)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class Shelf(models.Model):
    activitypub_id = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255)
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
                self.user.username,
                re.sub(r'\W', '-', self.name).lower()
            )
        if not self.activitypub_id:
            self.activitypub_id = 'https://%s/shelf/%s' % (DOMAIN, self.identifier)
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
    ''' a non-canonical copy from open library '''
    activitypub_id = models.CharField(max_length=255)
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    works = models.ManyToManyField('Work')
    authors = models.ManyToManyField('Author')
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
        self.activitypub_id = '%s%s' % (OL_URL, self.openlibary_key)
        super().save(*args, **kwargs)


class Work(models.Model):
    ''' encompassses all editions of a book '''
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

class Author(models.Model):
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

