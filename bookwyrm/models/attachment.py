''' media that is posted in the app '''
from django.db import models

from bookwyrm import activitypub
from .base_model import ActivitypubMixin
from .base_model import ActivityMapping, BookWyrmModel


class Attachment(ActivitypubMixin, BookWyrmModel):
    ''' an image (or, in the future, video etc) associated with a status '''
    status = models.ForeignKey(
        'Status',
        on_delete=models.CASCADE,
        related_name='attachments',
        null=True
    )
    class Meta:
        ''' one day we'll have other types of attachments besides images '''
        abstract = True

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('url', 'image'),
        ActivityMapping('name', 'caption'),
    ]

class Image(Attachment):
    ''' an image attachment '''
    image = models.ImageField(upload_to='status/', null=True, blank=True)
    caption = models.TextField(null=True, blank=True)

    activity_serializer = activitypub.Image
