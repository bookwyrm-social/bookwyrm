''' base model with default fields '''
from base64 import b64encode
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4
from urllib.parse import urlencode

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


    def to_ordered_collection(self, queryset, remote_id=None):
        ''' an ordered collection of whatevers '''
        remote_id = remote_id or self.remote_id
        size = queryset.count()
        return activitypub.Outbox(
            id=remote_id,
            totalItems=size,
            first='%s?page=true' % remote_id,
            last='%s?min_id=0&page=true' % remote_id
        ).serialize()


    def to_ordered_collection_page(self, queryset, \
            min_id=None, max_id=None, remote_id=None):
        ''' serialize and pagiante a queryset '''
        remote_id = remote_id or self.remote_id
        # TODO: weird place to define this
        limit = 20
        # filters for use in the django queryset min/max
        filters = {}
        # params for the url
        params = {'page': 'true'}
        if min_id is not None:
            params['min_id'] = min_id
            filters['id__gt'] = min_id
        if max_id is not None:
            params['max_id'] = max_id
            filters['id__lte'] = max_id
        page_id = remote_id + '?' + urlencode(params)

        items = queryset.filter(
            **filters
        ).all()[:limit]

        prev_page = next_page = ''
        if items.count():
            min_id = items[0].id
            max_id = items[len(items) - 1].id
            next_page = '%s?page=true&min_id=%d' % (remote_id, max_id)
            prev_page = '%s?page=true&max_id=%d' % (remote_id, min_id)
        return activitypub.OrderedCollectionPage(
            id=page_id,
            partOf=remote_id,
            orderedItems=[s.to_activity() for s in items],
            next=next_page,
            prev=prev_page,
        ).serialize()


@dataclass(frozen=True)
class ActivityMapping:
    ''' translate between an activitypub json field and a model field '''
    activity_key: str
    model_key: str
    activity_formatter: Callable = lambda x: x
    model_formatter: Callable = lambda x: x
