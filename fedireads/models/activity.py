''' models for storing different kinds of Activities '''
from django.contrib.postgres.fields import JSONField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from model_utils.managers import InheritanceManager


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
        if not self.activity_type:
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


class ReviewActivity(Activity):
    book = models.ForeignKey('Book', on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        self.activity_type = 'Article'
        super().save(*args, **kwargs)


class Status(models.Model):
    ''' reply to a review, etc '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    status_type = models.CharField(max_length=255, default='Note')
    activity = JSONField(max_length=5000, null=True)
    reply_parent = models.ForeignKey(
        'self',
        null=True,
        on_delete=models.PROTECT
    )
    content = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    objects = InheritanceManager()


class Review(Status):
    ''' a book review '''
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    rating = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    def save(self, *args, **kwargs):
        self.status_type = 'Review'
        super().save(*args, **kwargs)


