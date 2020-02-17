''' models for storing different kinds of Activities '''
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from model_utils.managers import InheritanceManager

from fedireads.utils.models import FedireadsModel


class Status(FedireadsModel):
    ''' any post, like a reply to a review, etc '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    status_type = models.CharField(max_length=255, default='Note')
    mention_users = models.ManyToManyField('User', related_name='mention_user')
    mention_books = models.ManyToManyField('Book', related_name='mention_book')
    activity_type = models.CharField(max_length=255, default='Note')
    local = models.BooleanField(default=True)
    privacy = models.CharField(max_length=255, default='public')
    sensitive = models.BooleanField(default=False)
    reply_parent = models.ForeignKey(
        'self',
        null=True,
        on_delete=models.PROTECT
    )
    objects = InheritanceManager()


class Review(Status):
    ''' a book review '''
    name = models.CharField(max_length=255)
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    rating = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    def save(self, *args, **kwargs):
        self.status_type = 'Review'
        super().save(*args, **kwargs)

