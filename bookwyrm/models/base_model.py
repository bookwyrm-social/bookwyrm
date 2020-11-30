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

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from .fields import RemoteIdField


PrivacyLevels = models.TextChoices('Privacy', [
    'public',
    'unlisted',
    'followers',
    'direct'
])

class BookWyrmModel(models.Model):
    ''' shared fields '''
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = RemoteIdField(null=True, activitypub_field='id')

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


def get_field_name(field):
    ''' model_field_name to activitypubFieldName '''
    if field.activitypub_field:
        return field.activitypub_field
    name = field.name.split('.')[-1]
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def unfurl_related_field(related_field):
    ''' load reverse lookups (like public key owner or Status attachment '''
    if hasattr(related_field, 'all'):
        return [unfurl_related_field(i) for i in related_field.all()]
    if related_field.reverse_unfurl:
        return related_field.to_activity()
    return related_field.remote_id


class ActivitypubMixin:
    ''' add this mixin for models that are AP serializable '''
    activity_serializer = lambda: {}
    reverse_unfurl = False

    def to_activity(self):
        ''' convert from a model to an activity '''
        activity = {}
        for field in self.__class__._meta.get_fields():
            if not hasattr(field, 'to_activity'):
                continue
            key = get_field_name(field)
            value = field.to_activity(getattr(self, field.name))
            if value is None:
                continue

            if key in activity and isinstance(activity[key], list):
                activity[key] += value
            else:
                activity[key] = value
        if hasattr(self, 'serialize_reverse_fields'):
            for field_name in self.serialize_reverse_fields:
                related_field = getattr(self, field_name)
                activity[field_name] = unfurl_related_field(related_field)

        return self.activity_serializer(**activity).serialize()


    def to_create_activity(self, user):
        ''' returns the object wrapped in a Create activity '''
        activity_object = self.to_activity()

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
            to=activity_object['to'],
            cc=activity_object['cc'],
            object=activity_object,
            signature=signature,
        ).serialize()


    def to_delete_activity(self, user):
        ''' notice of deletion '''
        # this should be a tombstone
        activity_object = self.to_activity()

        return activitypub.Delete(
            id=self.remote_id + '/activity',
            actor=user.remote_id,
            to=['%s/followers' % user.remote_id],
            cc=['https://www.w3.org/ns/activitystreams#Public'],
            object=activity_object,
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


class OrderedCollectionPageMixin(ActivitypubMixin):
    ''' just the paginator utilities, so you don't HAVE to
        override ActivitypubMixin's to_activity (ie, for outbox '''
    @property
    def collection_remote_id(self):
        ''' this can be overriden if there's a special remote id, ie outbox '''
        return self.remote_id

    def page(self, min_id=None, max_id=None):
        ''' helper function to create the pagination url '''
        params = {'page': 'true'}
        if min_id:
            params['min_id'] = min_id
        if max_id:
            params['max_id'] = max_id
        return '?%s' % urlencode(params)

    def next_page(self, items):
        ''' use the max id of the last item '''
        if not items.count():
            return ''
        return self.page(max_id=items[items.count() - 1].id)

    def prev_page(self, items):
        ''' use the min id of the first item '''
        if not items.count():
            return ''
        return self.page(min_id=items[0].id)

    def to_ordered_collection_page(self, queryset, remote_id, \
            id_only=False, min_id=None, max_id=None):
        ''' serialize and pagiante a queryset '''
        # TODO: weird place to define this
        limit = 20
        # filters for use in the django queryset min/max
        filters = {}
        if min_id is not None:
            filters['id__gt'] = min_id
        if max_id is not None:
            filters['id__lte'] = max_id
        page_id = self.page(min_id=min_id, max_id=max_id)

        items = queryset.filter(
            **filters
        ).all()[:limit]

        if id_only:
            page = [s.remote_id for s in items]
        else:
            page = [s.to_activity() for s in items]
        return activitypub.OrderedCollectionPage(
            id='%s%s' % (remote_id, page_id),
            partOf=remote_id,
            orderedItems=page,
            next='%s%s' % (remote_id, self.next_page(items)),
            prev='%s%s' % (remote_id, self.prev_page(items))
        ).serialize()

    def to_ordered_collection(self, queryset, \
            remote_id=None, page=False, **kwargs):
        ''' an ordered collection of whatevers '''
        remote_id = remote_id or self.remote_id
        if page:
            return self.to_ordered_collection_page(
                queryset, remote_id, **kwargs)
        name = ''
        if hasattr(self, 'name'):
            name = self.name
        owner = ''
        if hasattr(self, 'user'):
            owner = self.user.remote_id

        size = queryset.count()
        return activitypub.OrderedCollection(
            id=remote_id,
            totalItems=size,
            name=name,
            owner=owner,
            first='%s%s' % (remote_id, self.page()),
            last='%s%s' % (remote_id, self.page(min_id=0))
        ).serialize()


class OrderedCollectionMixin(OrderedCollectionPageMixin):
    ''' extends activitypub models to work as ordered collections '''
    @property
    def collection_queryset(self):
        ''' usually an ordered collection model aggregates a different model '''
        raise NotImplementedError('Model must define collection_queryset')

    activity_serializer = activitypub.OrderedCollection

    def to_activity(self, **kwargs):
        ''' an ordered collection of the specified model queryset  '''
        return self.to_ordered_collection(self.collection_queryset, **kwargs)


@dataclass(frozen=True)
class ActivityMapping:
    ''' translate between an activitypub json field and a model field '''
    activity_key: str
    model_key: str
    activity_formatter: Callable = lambda x: x
    model_formatter: Callable = lambda x: x
