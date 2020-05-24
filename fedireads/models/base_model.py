''' base model with default fields '''
from dataclasses import dataclass
from typing import Callable

from django.db import models
from django.db.models.fields.related_descriptors \
        import ForwardManyToOneDescriptor
from django.dispatch import receiver

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


class ActivitypubMixin:
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
    activity_serializer = lambda: {}

    def to_activity(self, pure=False):
        ''' convert from a model to an activity '''
        if pure:
            mappings = self.pure_activity_mappings
        else:
            mappings = self.activity_mappings

        fields = {}
        for mapping in mappings:
            if not hasattr(self, mapping.model_key):
                continue
            value = getattr(self, mapping.model_key)
            if hasattr(value, 'remote_id'):
                value = value.remote_id
            fields[mapping.activity_key] = mapping.formatter(value)

        return self.activity_serializer(
            **fields
        ).serialize()


def from_activity(model, activity):
    ''' convert from an activity to a model '''
    if not isinstance(activity, model.activity_serializer):
        raise TypeError('Wrong activity type for model')

    fields = {}
    for mapping in model.activity_mappings:
        value = getattr(activity, mapping.activity_key)
        model_field = getattr(model, mapping.model_key)

        # remote_id -> foreign key resolver
        if isinstance(model_field, ForwardManyToOneDescriptor):
            fk_model = model_field.field.related_model
            value = resolve_foreign_key(fk_model, value)

        fields[mapping.model_key] = value
    return model.objects.create(**fields)


def resolve_foreign_key(model, remote_id):
    ''' look up the remote_id on an activity json field '''
    if hasattr(model.objects, 'select_subclasses'):
        return model.objects.select_subclasses().filter(
            remote_id=remote_id
        ).first()
    return model.objects.filter(
        remote_id=remote_id
    ).first()


@dataclass(frozen=True)
class ActivityMapping:
    ''' translate between an activitypub json field and a model field '''
    activity_key: str
    model_key: str
    formatter: Callable = lambda x: x
