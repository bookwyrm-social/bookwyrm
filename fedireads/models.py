''' database schema for the whole dang thing '''
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from Crypto.PublicKey import RSA
from Crypto import Random
from datetime import datetime

class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.CharField(max_length=255)
    public_key = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    followers = models.ManyToManyField('self', symmetrical=False)

    def save(self, *args, **kwargs):
        # give a new user keys
        if not self.private_key:
            random_generator = Random.new().read
            key = RSA.generate(1024, random_generator)
            self.private_key = key
            self.public_key = key.publickey()
        if not self.id:
            self.created_date = datetime.now()
        self.updated_date = datetime.now()

        super().save(*args, **kwargs)


class Message(models.Model):
    ''' any kind of user post, incl. reviews, replies, and status updates '''
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey('User', on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    content = JSONField(max_length=5000)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Review(Message):
    id = models.AutoField(primary_key=True)
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    star_rating = models.IntegerField(default=0)


class Shelf(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    books = models.ManyToManyField('Book', symmetrical=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class Book(models.Model):
    ''' a non-canonical copy from open library '''
    id = models.AutoField(primary_key=True)
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    works = models.ManyToManyField('Work')
    added_by = models.ForeignKey('User', on_delete=models.PROTECT, blank=True, null=True)
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

class Work(models.Model):
    id = models.AutoField(primary_key=True)
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    added_by = models.ForeignKey('User', on_delete=models.PROTECT, blank=True, null=True)
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
