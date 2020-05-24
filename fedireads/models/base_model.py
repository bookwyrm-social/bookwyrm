''' base model with default fields '''
from collections import namedtuple
from dataclasses import dataclass
from django.db import models
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor
from django.dispatch import receiver
from typing import Callable, List

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
    model_to_activity = [
        ('id', 'remote_id'),
        ('type', 'activity_type'),
    ]
    activity_to_model = [
        ('remote_id', 'id'),
        ('activity_type', 'type'),
    ]
    activity_serializer = None

    @property
    def to_activity(self):
        fields = {k: getattr(self, v) for k, v in self.model_to_activity}
        return self.activity_serializer(
            **fields
        ).serialize()


def from_activity(model, activity):
    if not isinstance(activity, model.activity_serializer):
        raise TypeError('Wrong activity type for model')

    fields = {}
    for mapping in model.activity_to_model:
        value = getattr(activity, mapping.activity_key)
        print(mapping.model_key)
        model_field = getattr(model, mapping.model_key)
        print(type(model_field))
        if isinstance(model_field, ForwardManyToOneDescriptor):
            formatter_model = model_field.field.related_model
            print(formatter_model)
            value = resolve_foreign_key(formatter_model, value)
        print(mapping.formatter(value))
        fields[mapping.model_key] = mapping.formatter(value)
    return model.objects.create(**fields)


def resolve_foreign_key(model, remote_id):
    if hasattr(model.objects, 'select_subclasses'):
        return model.objects.select_subclasses().filter(
            remote_id=remote_id
        ).first()
    return model.objects.filter(
        remote_id=remote_id
    ).first()


@dataclass(frozen=True)
class ActivityMapping:
    model_key: str
    activity_key: str
    formatter: Callable = lambda x: x

