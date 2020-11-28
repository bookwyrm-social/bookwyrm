''' base model with default fields '''
from datetime import datetime
from base64 import b64encode
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4
from urllib.parse import urlencode

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.db import models
from django.db.models.fields.files import ImageFileDescriptor
from django.db.models.fields.related_descriptors \
        import ManyToManyDescriptor
from django.dispatch import receiver

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN


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
            # works around bookwyrm-specific fields for vanilla AP services
            mappings = self.pure_activity_mappings
        else:
            # may include custom fields that bookwyrm instances will understand
            mappings = self.activity_mappings

        fields = {}
        for mapping in mappings:
            if not hasattr(self, mapping.model_key) or not mapping.activity_key:
                # this field on the model isn't serialized
                continue
            value = getattr(self, mapping.model_key)
            model_field_type = getattr(self.__class__, mapping.model_key)
            if hasattr(value, 'remote_id'):
                # this is probably a foreign key field, which we want to
                # serialize as just the remote_id url reference
                value = value.remote_id
            elif isinstance(model_field_type, ManyToManyDescriptor):
                value = [i.remote_id for i in value.all()]
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(model_field_type, ImageFileDescriptor):
                value = image_formatter(value)

            # run the custom formatter function set in the model
            formatted_value = mapping.activity_formatter(value)
            if mapping.activity_key in fields and \
                    isinstance(fields[mapping.activity_key], list):
                # there can be two database fields that map to the same AP list
                # this happens in status tags, which combines user and book tags
                fields[mapping.activity_key] += formatted_value
            else:
                fields[mapping.activity_key] = formatted_value

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


def tag_formatter(items, name_field, activity_type):
    ''' helper function to format lists of foreign keys into Tags '''
    tags = []
    for item in items.all():
        tags.append(activitypub.Link(
            href=item.remote_id,
            name=getattr(item, name_field),
            type=activity_type
        ))
    return tags


def image_formatter(image):
    ''' convert images into activitypub json '''
    if image and hasattr(image, 'url'):
        url = image.url
    else:
        return None
    url = 'https://%s%s' % (DOMAIN, url)
    return activitypub.Image(url=url)


def image_attachments_formatter(images):
    ''' create a list of image attachments '''
    return [image_formatter(i) for i in images]
