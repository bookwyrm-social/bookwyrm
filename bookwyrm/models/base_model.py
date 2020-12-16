''' base model with default fields '''
from base64 import b64encode
from functools import reduce
import operator
from uuid import uuid4

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.dispatch import receiver

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN, PAGE_LENGTH
from .fields import ImageField, ManyToManyField, RemoteIdField


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
#pylint: disable=unused-argument
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' set the remote_id after save (when the id is available) '''
    if not created or not hasattr(instance, 'get_remote_id'):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        instance.save()


def unfurl_related_field(related_field):
    ''' load reverse lookups (like public key owner or Status attachment '''
    if hasattr(related_field, 'all'):
        return [unfurl_related_field(i) for i in related_field.all()]
    if related_field.reverse_unfurl:
        return related_field.field_to_activity()
    return related_field.remote_id


class ActivitypubMixin:
    ''' add this mixin for models that are AP serializable '''
    activity_serializer = lambda: {}
    reverse_unfurl = False

    def __init__(self, *args, **kwargs):
        ''' collect some info on model fields '''
        self.image_fields = []
        self.many_to_many_fields = []
        self.simple_fields = [] # "simple"
        for field in self._meta.get_fields():
            if not hasattr(field, 'field_to_activity'):
                continue

            if isinstance(field, ImageField):
                self.image_fields.append(field)
            elif isinstance(field, ManyToManyField):
                self.many_to_many_fields.append(field)
            else:
                self.simple_fields.append(field)

        self.activity_fields = self.image_fields + \
                self.many_to_many_fields + self.simple_fields

        self.deserialize_reverse_fields = self.deserialize_reverse_fields \
                if hasattr(self, 'deserialize_reverse_fields') else []
        self.serialize_reverse_fields = self.serialize_reverse_fields \
                if hasattr(self, 'serialize_reverse_fields') else []

        super().__init__(*args, **kwargs)


    @classmethod
    def find_existing_by_remote_id(cls, remote_id):
        ''' look up a remote id in the db '''
        return cls.find_existing({'id': remote_id})

    @classmethod
    def find_existing(cls, data):
        ''' compare data to fields that can be used for deduplation.
        This always includes remote_id, but can also be unique identifiers
        like an isbn for an edition '''
        filters = []
        for field in cls._meta.get_fields():
            if not hasattr(field, 'deduplication_field') or \
                    not field.deduplication_field:
                continue

            value = data.get(field.activitypub_field)
            if not value:
                continue
            filters.append({field.name: value})

        if hasattr(cls, 'origin_id') and 'id' in data:
            # kinda janky, but this handles special case for books
            filters.append({'origin_id': data['id']})

        if not filters:
            # if there are no deduplication fields, it will match the first
            # item no matter what. this shouldn't happen but just in case.
            return None

        objects = cls.objects
        if hasattr(objects, 'select_subclasses'):
            objects = objects.select_subclasses()

        # an OR operation on all the match fields
        match = objects.filter(
            reduce(
                operator.or_, (Q(**f) for f in filters)
            )
        )
        # there OUGHT to be only one match
        return match.first()


    def to_activity(self):
        ''' convert from a model to an activity '''
        activity = {}
        for field in self.activity_fields:
            field.set_activity_from_field(activity, self)

        if hasattr(self, 'serialize_reverse_fields'):
            # for example, editions of a work
            for model_field_name, activity_field_name in \
                    self.serialize_reverse_fields:
                related_field = getattr(self, model_field_name)
                activity[activity_field_name] = \
                        unfurl_related_field(related_field)

        if not activity.get('id'):
            activity['id'] = self.get_remote_id()
        return self.activity_serializer(**activity).serialize()


    def to_create_activity(self, user, **kwargs):
        ''' returns the object wrapped in a Create activity '''
        activity_object = self.to_activity(**kwargs)

        signer = pkcs1_15.new(RSA.import_key(user.key_pair.private_key))
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
        return activitypub.Delete(
            id=self.remote_id + '/activity',
            actor=user.remote_id,
            to=['%s/followers' % user.remote_id],
            cc=['https://www.w3.org/ns/activitystreams#Public'],
            object=self.to_activity(),
        ).serialize()


    def to_update_activity(self, user):
        ''' wrapper for Updates to an activity '''
        activity_id = '%s#update/%s' % (self.remote_id, uuid4())
        return activitypub.Update(
            id=activity_id,
            actor=user.remote_id,
            to=['https://www.w3.org/ns/activitystreams#Public'],
            object=self.to_activity()
        ).serialize()


    def to_undo_activity(self, user):
        ''' undo an action '''
        return activitypub.Undo(
            id='%s#undo' % self.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        ).serialize()


class OrderedCollectionPageMixin(ActivitypubMixin):
    ''' just the paginator utilities, so you don't HAVE to
        override ActivitypubMixin's to_activity (ie, for outbox '''
    @property
    def collection_remote_id(self):
        ''' this can be overriden if there's a special remote id, ie outbox '''
        return self.remote_id


    def to_ordered_collection(self, queryset, \
            remote_id=None, page=False, **kwargs):
        ''' an ordered collection of whatevers '''
        remote_id = remote_id or self.remote_id
        if page:
            return to_ordered_collection_page(
                queryset, remote_id, **kwargs)
        name = self.name if hasattr(self, 'name') else None
        owner = self.user.remote_id if hasattr(self, 'user') else ''

        paginated = Paginator(queryset, PAGE_LENGTH)
        return activitypub.OrderedCollection(
            id=remote_id,
            totalItems=paginated.count,
            name=name,
            owner=owner,
            first='%s?page=1' % remote_id,
            last='%s?page=%d' % (remote_id, paginated.num_pages)
        ).serialize()


def to_ordered_collection_page(queryset, remote_id, id_only=False, page=1):
    ''' serialize and pagiante a queryset '''
    paginated = Paginator(queryset, PAGE_LENGTH)

    activity_page = paginated.page(page)
    if id_only:
        items = [s.remote_id for s in activity_page.object_list]
    else:
        items = [s.to_activity() for s in activity_page.object_list]

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = '%s?page=%d' % (remote_id, activity_page.next_page_number())
    if activity_page.has_previous():
        prev_page = '%s?page=%d' % \
                (remote_id, activity_page.previous_page_number())
    return activitypub.OrderedCollectionPage(
        id='%s?page=%s' % (remote_id, page),
        partOf=remote_id,
        orderedItems=items,
        next=next_page,
        prev=prev_page
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
