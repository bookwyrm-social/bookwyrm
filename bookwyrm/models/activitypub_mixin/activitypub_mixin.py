''' base model with default fields '''
from base64 import b64encode
from functools import reduce
import json
import operator
from uuid import uuid4
import requests

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.apps import apps
from django.db import models
from django.db.models import Q
from django.dispatch import receiver
from django.utils.http import http_date


from bookwyrm import activitypub
from bookwyrm.settings import USER_AGENT
from bookwyrm.signatures import make_signature, make_digest
from bookwyrm.tasks import app
from .fields import ImageField, ManyToManyField


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


    def delete(self, *args, **kwargs):
        ''' broadcast suitable delete activities '''


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


    def to_undo_activity(self, user):
        ''' undo an action '''
        return activitypub.Undo(
            id='%s#undo' % self.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        ).serialize()




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
    if user and not user.local:
        # we don't want to broadcast when we save remote activities
        return

    if created:
        if not user:
            # book data and users don't need to broadcast on creation
            return

        # ordered collection items get "Add"ed
        if hasattr(instance, 'to_add_activity'):
            activity = instance.to_add_activity()
        else:
            # everything else gets "Create"d
            activity = instance.to_create_activity(user)
    else:
        # now, handle updates
        if not user:
            # users don't have associated users, they ARE users
            if sender.__class__ == 'User':
                user = instance
            # book data trakcs last editor
            elif hasattr(instance, 'last_edited_by'):
                user = instance.last_edited_by
        # again, if we don't know the user or they're remote, don't bother
        if not user or not user.local:
            return
        activity = instance.to_update_activity(user)

    if activity and user and user.local:
        instance.broadcast(activity, user)
