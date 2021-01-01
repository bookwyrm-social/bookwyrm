''' progress in a book '''
from django.db import models
from django.utils import timezone

from .base_model import BookWyrmModel


class ReadThrough(BookWyrmModel):
    ''' Store progress through a book in the database. '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    pages_read = models.IntegerField(
        null=True,
        blank=True)
    start_date = models.DateTimeField(
        blank=True,
        null=True)
    finish_date = models.DateTimeField(
        blank=True,
        null=True)

    def save(self, *args, **kwargs):
        ''' update user active time '''
        self.user.last_active_date = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)
