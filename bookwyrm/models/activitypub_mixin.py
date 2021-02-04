''' activitypub model functionality '''
from functools import reduce
import json
import operator
from base64 import b64encode
from uuid import uuid4
import requests

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.apps import apps
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.dispatch import receiver
from django.utils.http import http_date

from bookwyrm import activitypub
from bookwyrm.settings import USER_AGENT, PAGE_LENGTH
from bookwyrm.signatures import make_signature, make_digest
from bookwyrm.tasks import app
from bookwyrm.models.fields import ImageField, ManyToManyField


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

            value = data.get(field.get_activitypub_field())
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


    def broadcast(self, activity, sender, software=None):
        ''' send out an activity '''
        broadcast_task.delay(
            sender.id,
            json.dumps(activity, cls=activitypub.ActivityEncoder),
            self.get_recipients(software=software)
        )


    def get_recipients(self, software=None):
        ''' figure out which inbox urls to post to '''
        # first we have to figure out who should receive this activity
        privacy = self.privacy if hasattr(self, 'privacy') else 'public'
        # is this activity owned by a user (statuses, lists, shelves), or is it
        # general to the instance (like books)
        user = self.user if hasattr(self, 'user') else None
        if not user and self.__model__ == 'user':
            # or maybe the thing itself is a user
            user = self
        # find anyone who's tagged in a status, for example
        mentions = self.mention_users if hasattr(self, 'mention_users') else []

        # we always send activities to explicitly mentioned users' inboxes
        recipients = [u.inbox for u in mentions or []]

        # unless it's a dm, all the followers should receive the activity
        if privacy != 'direct':
            user_model = apps.get_model('bookwyrm.User', require_ready=True)
            # filter users first by whether they're using the desired software
            # this lets us send book updates only to other bw servers
            queryset = user_model.objects.filter(
                bookwyrm_user=(software == 'bookwyrm')
            )
            # if there's a user, we only want to send to the user's followers
            if user:
                queryset = queryset.filter(following=user)

            # ideally, we will send to shared inboxes for efficiency
            shared_inboxes = queryset.filter(
                shared_inbox__isnull=False
            ).values_list('shared_inbox', flat=True).distinct()
            # but not everyone has a shared inbox
            inboxes = queryset.filter(
                shared_inboxes__isnull=True
            ).values_list('inbox', flat=True)
            recipients += list(shared_inboxes) + list(inboxes)
        return recipients


    def to_activity(self):
        ''' convert from a model to an activity '''
        activity = generate_activity(self)
        return self.activity_serializer(**activity).serialize()


def generate_activity(obj):
    ''' go through the fields on an object '''
    activity = {}
    for field in obj.activity_fields:
        field.set_activity_from_field(activity, obj)

    if hasattr(obj, 'serialize_reverse_fields'):
        # for example, editions of a work
        for model_field_name, activity_field_name, sort_field in \
                obj.serialize_reverse_fields:
            related_field = getattr(obj, model_field_name)
            activity[activity_field_name] = \
                    unfurl_related_field(related_field, sort_field)

    if not activity.get('id'):
        activity['id'] = obj.get_remote_id()
    return activity


def unfurl_related_field(related_field, sort_field=None):
    ''' load reverse lookups (like public key owner or Status attachment '''
    if hasattr(related_field, 'all'):
        return [unfurl_related_field(i) for i in related_field.order_by(
            sort_field).all()]
    if related_field.reverse_unfurl:
        return related_field.field_to_activity()
    return related_field.remote_id


@app.task
def broadcast_task(sender_id, activity, recipients):
    ''' the celery task for broadcast '''
    user_model = apps.get_model('bookwyrm.User', require_ready=True)
    sender = user_model.objects.get(id=sender_id)
    errors = []
    for recipient in recipients:
        try:
            sign_and_send(sender, activity, recipient)
        except requests.exceptions.HTTPError as e:
            errors.append({
                'error': str(e),
                'recipient': recipient,
                'activity': activity,
            })
    return errors


def sign_and_send(sender, data, destination):
    ''' crpyto whatever and http junk '''
    now = http_date()

    if not sender.key_pair.private_key:
        # this shouldn't happen. it would be bad if it happened.
        raise ValueError('No private key found for sender')

    digest = make_digest(data)

    response = requests.post(
        destination,
        data=data,
        headers={
            'Date': now,
            'Digest': digest,
            'Signature': make_signature(sender, destination, now, digest),
            'Content-Type': 'application/activity+json; charset=utf-8',
            'User-Agent': USER_AGENT,
        },
    )
    if not response.ok:
        response.raise_for_status()
    return response


@receiver(models.signals.post_save)
#pylint: disable=unused-argument
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' broadcast when a model instance is created or updated '''
    # user content like statuses, lists, and shelves, have a "user" field
    user = instance.user if hasattr(instance, 'user') else None

    # we don't want to broadcast when we save remote activities
    if user and not user.local:
        return

    if created:
        # book data and users don't need to broadcast on creation
        if not user:
            return

        # ordered collection items get "Add"ed
        if hasattr(instance, 'to_add_activity'):
            activity = instance.to_add_activity()
        else:
            # everything else gets "Create"d
            activity = instance.to_create_activity(user)

    if activity and user and user.local:
        instance.broadcast(activity, user)


class ObjectMixin(ActivitypubMixin):
    ''' add this mixin for object models that are AP serializable '''

    def save(self, *args, **kwargs):
        ''' broadcast updated '''
        # first off, we want to save normally no matter what
        super().save(*args, **kwargs)

        # we only want to handle updates, not newly created objects
        if not self.id:
            return

        # this will work for lists, shelves
        user = self.user if hasattr(self, 'user') else None
        if not user:
            # users don't have associated users, they ARE users
            user_model = apps.get_model('bookwyrm.User', require_ready=True)
            if isinstance(self, user_model):
                user = self
            # book data tracks last editor
            elif hasattr(self, 'last_edited_by'):
                user = self.last_edited_by
        # again, if we don't know the user or they're remote, don't bother
        if not user or not user.local:
            return

        # is this a deletion?
        if self.deleted:
            activity = self.to_delete_activity(user)
        else:
            activity = self.to_update_activity(user)
        self.broadcast(activity, user)


    def to_create_activity(self, user, **kwargs):
        ''' returns the object wrapped in a Create activity '''
        activity_object = self.to_activity(**kwargs)

        signature = None
        create_id = self.remote_id + '/activity'
        if 'content' in activity_object:
            signer = pkcs1_15.new(RSA.import_key(user.key_pair.private_key))
            content = activity_object['content']
            signed_message = signer.sign(SHA256.new(content.encode('utf8')))

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


class OrderedCollectionPageMixin(ObjectMixin):
    ''' just the paginator utilities, so you don't HAVE to
        override ActivitypubMixin's to_activity (ie, for outbox) '''
    @property
    def collection_remote_id(self):
        ''' this can be overriden if there's a special remote id, ie outbox '''
        return self.remote_id


    def to_ordered_collection(self, queryset, \
            remote_id=None, page=False, collection_only=False, **kwargs):
        ''' an ordered collection of whatevers '''
        if not queryset.ordered:
            raise RuntimeError('queryset must be ordered')

        remote_id = remote_id or self.remote_id
        if page:
            return to_ordered_collection_page(
                queryset, remote_id, **kwargs)

        if collection_only or not hasattr(self, 'activity_serializer'):
            serializer = activitypub.OrderedCollection
            activity = {}
        else:
            serializer = self.activity_serializer
            # a dict from the model fields
            activity = generate_activity(self)

        if remote_id:
            activity['id'] = remote_id

        paginated = Paginator(queryset, PAGE_LENGTH)
        # add computed fields specific to orderd collections
        activity['totalItems'] = paginated.count
        activity['first'] = '%s?page=1' % remote_id
        activity['last'] = '%s?page=%d' % (remote_id, paginated.num_pages)

        return serializer(**activity).serialize()


# pylint: disable=unused-argument
def to_ordered_collection_page(
        queryset, remote_id, id_only=False, page=1, **kwargs):
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


class CollectionItemMixin(ActivitypubMixin):
    ''' for items that are part of an (Ordered)Collection '''
    activity_serializer = activitypub.Add
    object_field = collection_field = None

    def to_add_activity(self):
        ''' AP for shelving a book'''
        object_field = getattr(self, self.object_field)
        collection_field = getattr(self, self.collection_field)
        return activitypub.Add(
            id='%s#add' % self.remote_id,
            actor=self.user.remote_id,
            object=object_field.to_activity(),
            target=collection_field.remote_id
        ).serialize()

    def to_remove_activity(self):
        ''' AP for un-shelving a book'''
        object_field = getattr(self, self.object_field)
        collection_field = getattr(self, self.collection_field)
        return activitypub.Remove(
            id='%s#remove' % self.remote_id,
            actor=self.user.remote_id,
            object=object_field.to_activity(),
            target=collection_field.remote_id
        ).serialize()


class ActivitybMixin(ActivitypubMixin):
    ''' add this mixin for models that are AP serializable '''

    def save(self, *args, **kwargs):
        ''' broadcast activity '''
        super().save(*args, **kwargs)
        self.broadcast(self.to_activity(), self.user)

    def delete(self, *args, **kwargs):
        ''' nevermind, undo that activity '''
        self.broadcast(self.to_undo_activity(), self.user)
        super().delete(*args, **kwargs)


    def to_undo_activity(self):
        ''' undo an action '''
        return activitypub.Undo(
            id='%s#undo' % self.remote_id,
            actor=self.user.remote_id,
            object=self.to_activity()
        ).serialize()
