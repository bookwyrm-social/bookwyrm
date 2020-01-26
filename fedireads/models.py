''' database schema for the whole dang thing '''
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from Crypto.PublicKey import RSA
from Crypto import Random
from fedireads.settings import DOMAIN

class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.CharField(max_length=1024)
    public_key = models.CharField(max_length=1024)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    actor = JSONField()
    local = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    followers = models.ManyToManyField('self', symmetrical=False)

    def save(self, *args, **kwargs):
        # give a new user keys
        if not self.private_key:
            random_generator = Random.new().read
            key = RSA.generate(1024, random_generator)
            self.private_key = key.export_key()
            self.public_key = key.publickey().export_key()

        if self.local and not self.actor:
            self.actor = {
                '@context': [
                    'https://www.w3.org/ns/activitystreams',
                    'https://w3id.org/security/v1'
                ],

                'id': 'https://%s/u/%s' % (DOMAIN, self.username),
                'type': 'Person',
                'preferredUsername': self.username,
                'inbox': 'https://%s/api/inbox' % DOMAIN,
                'followers': 'https://%s/u/%s/followers' % \
                        (DOMAIN, self.username),
                'publicKey': {
                    'id': 'https://%s/u/%s#main-key' % (DOMAIN, self.username),
                    'owner': 'https://%s/u/%s' % (DOMAIN, self.username),
                    'publicKeyPem': self.public_key.decode('utf8'),
                }
            }

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
    author = models.ForeignKey('User', on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    content = JSONField(max_length=5000)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Review(Message):
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    star_rating = models.IntegerField(default=0)


class Activity(models.Model):
    data = JSONField()
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    remote = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)


class Shelf(models.Model):
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


class Book(models.Model):
    ''' a non-canonical copy from open library '''
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

