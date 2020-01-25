''' database schema for the whole dang thing '''
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField

class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.CharField(max_length=255)
    public_key = models.CharField(max_length=255)
    webfinger = JSONField(max_length=255)
    actor = JSONField(max_length=255, blank=True, null=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    followers = models.CharField(max_length=255, blank=True, null=True)
    messages = models.CharField(max_length=255, blank=True, null=True)
    created_date = models.DateTimeField()
    updated_date = models.DateTimeField(blank=True, null=True)


class Message(models.Model):
    ''' any kind of user post, incl. reviews, replies, and status updates '''
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey('User', on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    content = JSONField(max_length=5000)

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


class Book(models.Model):
    ''' a non-canonical copy from open library '''
    id = models.AutoField(primary_key=True)
    openlibary_key = models.CharField(max_length=255)
    data = JSONField()
    added_date = models.DateTimeField()
    updated_date = models.DateTimeField(blank=True, null=True)


class ShelfBooks(models.Model):
    ''' many to many join table '''
    id = models.AutoField(primary_key=True)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
