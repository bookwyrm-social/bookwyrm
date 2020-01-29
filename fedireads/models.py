''' database schema for the whole dang thing '''
from django.db import models
from model_utils.managers import InheritanceManager
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from Crypto import Random
from Crypto.PublicKey import RSA
import re

from fedireads.settings import DOMAIN, OL_URL


class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.TextField(blank=True, null=True, unique=True)
    public_key = models.TextField(blank=True, null=True, unique=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    actor = models.CharField(max_length=255, unique=True)
    inbox = models.CharField(max_length=255, unique=True)
    shared_inbox = models.CharField(max_length=255)
    outbox = models.CharField(max_length=255, unique=True)
    summary = models.TextField(blank=True, null=True)
    local = models.BooleanField(default=True)
    localname = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True
    )
    avatar = models.ImageField(upload_to='uploads/', blank=True, null=True)
    # TODO: a field for if non-local users are readers or others
    followers = models.ManyToManyField('self', symmetrical=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


@receiver(models.signals.pre_save, sender=User)
def execute_before_save(sender, instance, *args, **kwargs):
    ''' create shelves for new users '''
    # this user already exists, no need to poplate fields
    if instance.id:
        return

    # TODO: how do I know this properly???
    if not instance.local:
        instance.inbox = instance.actor = 'inbox'
        instance.outbox = instance.actor = 'outbox'
        return

    # populate fields for local users
    instance.localname = instance.username
    instance.username = '%s@%s' % (instance.username, DOMAIN)
    instance.actor = 'https://%s/user/%s' % (DOMAIN, instance.localname)
    instance.inbox = 'https://%s/user/%s/inbox' % (DOMAIN, instance.localname)
    instance.shared_inbox = 'https://%s/inbox' % DOMAIN
    instance.outbox = 'https://%s/user/%s/outbox' % (DOMAIN, instance.localname)
    if not instance.private_key:
        random_generator = Random.new().read
        key = RSA.generate(1024, random_generator)
        instance.private_key = key.export_key().decode('utf8')
        instance.public_key = key.publickey().export_key().decode('utf8')


@receiver(models.signals.post_save, sender=User)
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' create shelves for new users '''
    # TODO: how are remote users handled? what if they aren't readers?
    if not instance.local or not created:
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


class Activity(models.Model):
    ''' basic fields for storing activities '''
    uuid = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    content = JSONField(max_length=5000)
    # the activitypub activity type (Create, Add, Follow, ...)
    activity_type = models.CharField(max_length=255)
    # custom types internal to fedireads (Review, Shelve, ...)
    fedireads_type = models.CharField(max_length=255, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    objects = InheritanceManager()


class ShelveActivity(Activity):
    ''' someone put a book on a shelf '''
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        self.activity_type = 'Add'
        self.fedireads_type = 'Shelve'
        super().save(*args, **kwargs)


class FollowActivity(Activity):
    ''' record follow requests sent out '''
    followed = models.ForeignKey(
        'User',
        related_name='followed',
        on_delete=models.PROTECT
    )

    def save(self, *args, **kwargs):
        self.activity_type = 'Follow'
        super().save(*args, **kwargs)


class Review(Activity):
    ''' a book review '''
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    work = models.ForeignKey('Work', on_delete=models.PROTECT)
    name = models.TextField()
    # TODO: validation
    rating = models.IntegerField(default=0)
    review_content = models.TextField()

    def save(self, *args, **kwargs):
        self.activity_type = 'Article'
        self.fedireads_type = 'Review'
        super().save(*args, **kwargs)


class Note(Activity):
    ''' reply to a review, etc '''
    def save(self, *args, **kwargs):
        self.activity_type = 'Note'
        super().save(*args, **kwargs)


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
    ''' a non-canonical copy from open library '''
    activitypub_id = models.CharField(max_length=255)
    openlibrary_key = models.CharField(max_length=255, unique=True)
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
        self.activitypub_id = '%s%s' % (OL_URL, self.openlibrary_key)
        super().save(*args, **kwargs)


class Work(models.Model):
    ''' encompassses all editions of a book '''
    openlibrary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class Author(models.Model):
    openlibrary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

