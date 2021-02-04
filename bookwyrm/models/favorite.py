''' like/fav/star a status '''
from django.db import models
from django.utils import timezone

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from . import fields

class Favorite(ActivitypubMixin, BookWyrmModel):
    ''' fav'ing a post '''
    user = fields.ForeignKey(
        'User', on_delete=models.PROTECT, activitypub_field='actor')
    status = fields.ForeignKey(
        'Status', on_delete=models.PROTECT, activitypub_field='object')

    activity_serializer = activitypub.Like

    def save(self, *args, **kwargs):
        ''' update user active time '''
        self.user.last_active_date = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)

    class Meta:
        ''' can't fav things twice '''
        unique_together = ('user', 'status')
