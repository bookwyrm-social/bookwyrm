''' base model with default fields '''
from django.db import models
from django.dispatch import receiver
from typing import List

from fedireads.settings import DOMAIN

class FedireadsModel(models.Model):
    ''' shared fields '''
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = models.CharField(max_length=255, null=True)

    def get_remote_id(self):
        ''' generate a url that resolves to the local object '''
        base_path = 'https://%s' % DOMAIN
        if hasattr(self, 'user'):
            base_path = self.user.remote_id
        model_name = type(self).__name__.lower()
        return '%s/%s/%d' % (base_path, model_name, self.id)

    class Meta:
        abstract = True


@receiver(models.signals.post_save)
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' set the remote_id after save (when the id is available) '''
    if not created or not hasattr(instance, 'get_remote_id'):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        instance.save()


class ActivitypubMixin(object):
    ''' add this mixin for models that are AP serializable '''
    activity_type = 'Object'
    activity_fields = [
        ('id', 'remote_id'),
        ('type', 'activity_type'),
    ]
    activity_serializer = None

    @property
    def activitypub_serialize(self):
        fields = {k: getattr(self, v) for k, v in self.activity_fields}
        return self.activity_serializer(
            **fields
        ).serialize()
