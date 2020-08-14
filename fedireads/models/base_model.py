''' base model with default fields '''
from base64 import b64encode
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.db import models
from django.dispatch import receiver

from fedireads import activitypub
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
        ''' this is just here to provide default fields for other models '''
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
    activity_serializer = lambda: {}

    def to_activity(self, pure=False):
        ''' convert from a model to an activity '''
        if pure:
            mappings = self.pure_activity_mappings
        else:
            mappings = self.activity_mappings

        fields = {}
        for mapping in mappings:
            if not hasattr(self, mapping.model_key) or not mapping.activity_key:
                continue
            value = getattr(self, mapping.model_key)
            if hasattr(value, 'remote_id'):
                value = value.remote_id
            fields[mapping.activity_key] = mapping.activity_formatter(value)

        if pure:
            return self.pure_activity_serializer(
                **fields
            ).serialize()
        return self.activity_serializer(
            **fields
        ).serialize()


    def to_create_activity(self, user, pure=False):
        ''' returns the object wrapped in a Create activity '''
        activity_object = self.to_activity(pure=pure)

        signer = pkcs1_15.new(RSA.import_key(user.private_key))
        content = activity_object['content']
        signed_message = signer.sign(SHA256.new(content.encode('utf8')))
        create_id = self.remote_id + '/activity'

        signature = activitypub.Signature(
            creator='%s#main-key' % user.remote_id,
            created=activity_object['published'],
            signatureValue=b64encode(signed_message).decode('utf8')
        )

        return activitypub.Create(
            id=create_id,
            actor=user.remote_id,
            to=['%s/followers' % user.remote_id],
            cc=['https://www.w3.org/ns/activitystreams#Public'],
            object=activity_object,
            signature=signature,
        ).serialize()


    def to_update_activity(self, user):
        ''' wrapper for Updates to an activity '''
        activity_id = '%s#update/%s' % (user.remote_id, uuid4())
        return activitypub.Update(
            id=activity_id,
            actor=user.remote_id,
            to=['https://www.w3.org/ns/activitystreams#Public'],
            object=self.to_activity()
        ).serialize()


    def to_undo_activity(self, user):
        ''' undo an action '''
        return activitypub.Undo(
            id='%s#undo' % user.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        )


@dataclass(frozen=True)
class ActivityMapping:
    ''' translate between an activitypub json field and a model field '''
    activity_key: str
    model_key: str
    activity_formatter: Callable = lambda x: x
    model_formatter: Callable = lambda x: x
