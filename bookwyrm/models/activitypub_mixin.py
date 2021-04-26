""" activitypub model functionality """
from base64 import b64encode
from collections import namedtuple
from functools import reduce
import json
import operator
import logging
from uuid import uuid4
import requests
from requests.exceptions import HTTPError, SSLError

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.apps import apps
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.http import http_date

from bookwyrm import activitypub
from bookwyrm.settings import USER_AGENT, PAGE_LENGTH
from bookwyrm.signatures import make_signature, make_digest
from bookwyrm.tasks import app
from bookwyrm.models.fields import ImageField, ManyToManyField

logger = logging.getLogger(__name__)
# I tried to separate these classes into mutliple files but I kept getting
# circular import errors so I gave up. I'm sure it could be done though!

PropertyField = namedtuple("PropertyField", ("set_activity_from_field"))


def set_activity_from_property_field(activity, obj, field):
    """assign a model property value to the activity json"""
    activity[field[1]] = getattr(obj, field[0])


class ActivitypubMixin:
    """add this mixin for models that are AP serializable"""

    activity_serializer = lambda: {}
    reverse_unfurl = False

    def __init__(self, *args, **kwargs):
        """collect some info on model fields"""
        self.image_fields = []
        self.many_to_many_fields = []
        self.simple_fields = []  # "simple"
        # sort model fields by type
        for field in self._meta.get_fields():
            if not hasattr(field, "field_to_activity"):
                continue

            if isinstance(field, ImageField):
                self.image_fields.append(field)
            elif isinstance(field, ManyToManyField):
                self.many_to_many_fields.append(field)
            else:
                self.simple_fields.append(field)

        # a list of allll the serializable fields
        self.activity_fields = (
            self.image_fields + self.many_to_many_fields + self.simple_fields
        )
        if hasattr(self, "property_fields"):
            self.activity_fields += [
                # pylint: disable=cell-var-from-loop
                PropertyField(lambda a, o: set_activity_from_property_field(a, o, f))
                for f in self.property_fields
            ]

        # these are separate to avoid infinite recursion issues
        self.deserialize_reverse_fields = (
            self.deserialize_reverse_fields
            if hasattr(self, "deserialize_reverse_fields")
            else []
        )
        self.serialize_reverse_fields = (
            self.serialize_reverse_fields
            if hasattr(self, "serialize_reverse_fields")
            else []
        )

        super().__init__(*args, **kwargs)

    @classmethod
    def find_existing_by_remote_id(cls, remote_id):
        """look up a remote id in the db"""
        return cls.find_existing({"id": remote_id})

    @classmethod
    def find_existing(cls, data):
        """compare data to fields that can be used for deduplation.
        This always includes remote_id, but can also be unique identifiers
        like an isbn for an edition"""
        filters = []
        # grabs all the data from the model to create django queryset filters
        for field in cls._meta.get_fields():
            if (
                not hasattr(field, "deduplication_field")
                or not field.deduplication_field
            ):
                continue

            value = data.get(field.get_activitypub_field())
            if not value:
                continue
            filters.append({field.name: value})

        if hasattr(cls, "origin_id") and "id" in data:
            # kinda janky, but this handles special case for books
            filters.append({"origin_id": data["id"]})

        if not filters:
            # if there are no deduplication fields, it will match the first
            # item no matter what. this shouldn't happen but just in case.
            return None

        objects = cls.objects
        if hasattr(objects, "select_subclasses"):
            objects = objects.select_subclasses()

        # an OR operation on all the match fields, sorry for the dense syntax
        match = objects.filter(reduce(operator.or_, (Q(**f) for f in filters)))
        # there OUGHT to be only one match
        return match.first()

    def broadcast(self, activity, sender, software=None):
        """send out an activity"""
        broadcast_task.delay(
            sender.id,
            json.dumps(activity, cls=activitypub.ActivityEncoder),
            self.get_recipients(software=software),
        )

    def get_recipients(self, software=None):
        """figure out which inbox urls to post to"""
        # first we have to figure out who should receive this activity
        privacy = self.privacy if hasattr(self, "privacy") else "public"
        # is this activity owned by a user (statuses, lists, shelves), or is it
        # general to the instance (like books)
        user = self.user if hasattr(self, "user") else None
        user_model = apps.get_model("bookwyrm.User", require_ready=True)
        if not user and isinstance(self, user_model):
            # or maybe the thing itself is a user
            user = self
        # find anyone who's tagged in a status, for example
        mentions = self.recipients if hasattr(self, "recipients") else []

        # we always send activities to explicitly mentioned users' inboxes
        recipients = [u.inbox for u in mentions or [] if not u.local]

        # unless it's a dm, all the followers should receive the activity
        if privacy != "direct":
            # we will send this out to a subset of all remote users
            queryset = (
                user_model.viewer_aware_objects(user)
                .filter(
                    local=False,
                )
                .distinct()
            )
            # filter users first by whether they're using the desired software
            # this lets us send book updates only to other bw servers
            if software:
                queryset = queryset.filter(bookwyrm_user=(software == "bookwyrm"))
            # if there's a user, we only want to send to the user's followers
            if user:
                queryset = queryset.filter(following=user)

            # ideally, we will send to shared inboxes for efficiency
            shared_inboxes = (
                queryset.filter(shared_inbox__isnull=False)
                .values_list("shared_inbox", flat=True)
                .distinct()
            )
            # but not everyone has a shared inbox
            inboxes = queryset.filter(shared_inbox__isnull=True).values_list(
                "inbox", flat=True
            )
            recipients += list(shared_inboxes) + list(inboxes)
        return list(set(recipients))

    def to_activity_dataclass(self):
        """convert from a model to an activity"""
        activity = generate_activity(self)
        return self.activity_serializer(**activity)

    def to_activity(self, **kwargs):  # pylint: disable=unused-argument
        """convert from a model to a json activity"""
        return self.to_activity_dataclass().serialize()


class ObjectMixin(ActivitypubMixin):
    """add this mixin for object models that are AP serializable"""

    def save(self, *args, created=None, **kwargs):
        """broadcast created/updated/deleted objects as appropriate"""
        broadcast = kwargs.get("broadcast", True)
        # this bonus kwarg would cause an error in the base save method
        if "broadcast" in kwargs:
            del kwargs["broadcast"]

        created = created or not bool(self.id)
        # first off, we want to save normally no matter what
        super().save(*args, **kwargs)
        if not broadcast or (
            hasattr(self, "status_type") and self.status_type == "Announce"
        ):
            return

        # this will work for objects owned by a user (lists, shelves)
        user = self.user if hasattr(self, "user") else None

        if created:
            # broadcast Create activities for objects owned by a local user
            if not user or not user.local:
                return

            try:
                software = None
                # do we have a "pure" activitypub version of this for mastodon?
                if hasattr(self, "pure_content"):
                    pure_activity = self.to_create_activity(user, pure=True)
                    self.broadcast(pure_activity, user, software="other")
                    software = "bookwyrm"
                # sends to BW only if we just did a pure version for masto
                activity = self.to_create_activity(user)
                self.broadcast(activity, user, software=software)
            except AttributeError:
                # janky as heck, this catches the mutliple inheritence chain
                # for boosts and ignores this auxilliary broadcast
                return
            return

        # --- updating an existing object
        if not user:
            # users don't have associated users, they ARE users
            user_model = apps.get_model("bookwyrm.User", require_ready=True)
            if isinstance(self, user_model):
                user = self
            # book data tracks last editor
            elif hasattr(self, "last_edited_by"):
                user = self.last_edited_by
        # again, if we don't know the user or they're remote, don't bother
        if not user or not user.local:
            return

        # is this a deletion?
        if hasattr(self, "deleted") and self.deleted:
            activity = self.to_delete_activity(user)
        else:
            activity = self.to_update_activity(user)
        self.broadcast(activity, user)

    def to_create_activity(self, user, **kwargs):
        """returns the object wrapped in a Create activity"""
        activity_object = self.to_activity_dataclass(**kwargs)

        signature = None
        create_id = self.remote_id + "/activity"
        if hasattr(activity_object, "content") and activity_object.content:
            signer = pkcs1_15.new(RSA.import_key(user.key_pair.private_key))
            content = activity_object.content
            signed_message = signer.sign(SHA256.new(content.encode("utf8")))

            signature = activitypub.Signature(
                creator="%s#main-key" % user.remote_id,
                created=activity_object.published,
                signatureValue=b64encode(signed_message).decode("utf8"),
            )

        return activitypub.Create(
            id=create_id,
            actor=user.remote_id,
            to=activity_object.to,
            cc=activity_object.cc,
            object=activity_object,
            signature=signature,
        ).serialize()

    def to_delete_activity(self, user):
        """notice of deletion"""
        return activitypub.Delete(
            id=self.remote_id + "/activity",
            actor=user.remote_id,
            to=["%s/followers" % user.remote_id],
            cc=["https://www.w3.org/ns/activitystreams#Public"],
            object=self,
        ).serialize()

    def to_update_activity(self, user):
        """wrapper for Updates to an activity"""
        activity_id = "%s#update/%s" % (self.remote_id, uuid4())
        return activitypub.Update(
            id=activity_id,
            actor=user.remote_id,
            to=["https://www.w3.org/ns/activitystreams#Public"],
            object=self,
        ).serialize()


class OrderedCollectionPageMixin(ObjectMixin):
    """just the paginator utilities, so you don't HAVE to
    override ActivitypubMixin's to_activity (ie, for outbox)"""

    @property
    def collection_remote_id(self):
        """this can be overriden if there's a special remote id, ie outbox"""
        return self.remote_id

    def to_ordered_collection(
        self, queryset, remote_id=None, page=False, collection_only=False, **kwargs
    ):
        """an ordered collection of whatevers"""
        if not queryset.ordered:
            raise RuntimeError("queryset must be ordered")

        remote_id = remote_id or self.remote_id
        if page:
            return to_ordered_collection_page(queryset, remote_id, **kwargs)

        if collection_only or not hasattr(self, "activity_serializer"):
            serializer = activitypub.OrderedCollection
            activity = {}
        else:
            serializer = self.activity_serializer
            # a dict from the model fields
            activity = generate_activity(self)

        if remote_id:
            activity["id"] = remote_id

        paginated = Paginator(queryset, PAGE_LENGTH)
        # add computed fields specific to orderd collections
        activity["totalItems"] = paginated.count
        activity["first"] = "%s?page=1" % remote_id
        activity["last"] = "%s?page=%d" % (remote_id, paginated.num_pages)

        return serializer(**activity)


class OrderedCollectionMixin(OrderedCollectionPageMixin):
    """extends activitypub models to work as ordered collections"""

    @property
    def collection_queryset(self):
        """usually an ordered collection model aggregates a different model"""
        raise NotImplementedError("Model must define collection_queryset")

    activity_serializer = activitypub.OrderedCollection

    def to_activity_dataclass(self, **kwargs):
        return self.to_ordered_collection(self.collection_queryset, **kwargs)

    def to_activity(self, **kwargs):
        """an ordered collection of the specified model queryset"""
        return self.to_ordered_collection(
            self.collection_queryset, **kwargs
        ).serialize()


class CollectionItemMixin(ActivitypubMixin):
    """for items that are part of an (Ordered)Collection"""

    activity_serializer = activitypub.CollectionItem

    def broadcast(self, activity, sender, software="bookwyrm"):
        """only send book collection updates to other bookwyrm instances"""
        super().broadcast(activity, sender, software=software)

    @property
    def privacy(self):
        """inherit the privacy of the list, or direct if pending"""
        collection_field = getattr(self, self.collection_field)
        if self.approved:
            return collection_field.privacy
        return "direct"

    @property
    def recipients(self):
        """the owner of the list is a direct recipient"""
        collection_field = getattr(self, self.collection_field)
        if collection_field.user.local:
            # don't broadcast to yourself
            return []
        return [collection_field.user]

    def save(self, *args, broadcast=True, **kwargs):
        """broadcast updated"""
        # first off, we want to save normally no matter what
        super().save(*args, **kwargs)

        # list items can be updateda, normally you would only broadcast on created
        if not broadcast or not self.user.local:
            return

        # adding an obj to the collection
        activity = self.to_add_activity(self.user)
        self.broadcast(activity, self.user)

    def delete(self, *args, broadcast=True, **kwargs):
        """broadcast a remove activity"""
        activity = self.to_remove_activity(self.user)
        super().delete(*args, **kwargs)
        if self.user.local and broadcast:
            self.broadcast(activity, self.user)

    def to_add_activity(self, user):
        """AP for shelving a book"""
        collection_field = getattr(self, self.collection_field)
        return activitypub.Add(
            id="{:s}#add".format(collection_field.remote_id),
            actor=user.remote_id,
            object=self.to_activity_dataclass(),
            target=collection_field.remote_id,
        ).serialize()

    def to_remove_activity(self, user):
        """AP for un-shelving a book"""
        collection_field = getattr(self, self.collection_field)
        return activitypub.Remove(
            id="{:s}#remove".format(collection_field.remote_id),
            actor=user.remote_id,
            object=self.to_activity_dataclass(),
            target=collection_field.remote_id,
        ).serialize()


class ActivityMixin(ActivitypubMixin):
    """add this mixin for models that are AP serializable"""

    def save(self, *args, broadcast=True, **kwargs):
        """broadcast activity"""
        super().save(*args, **kwargs)
        user = self.user if hasattr(self, "user") else self.user_subject
        if broadcast and user.local:
            self.broadcast(self.to_activity(), user)

    def delete(self, *args, broadcast=True, **kwargs):
        """nevermind, undo that activity"""
        user = self.user if hasattr(self, "user") else self.user_subject
        if broadcast and user.local:
            self.broadcast(self.to_undo_activity(), user)
        super().delete(*args, **kwargs)

    def to_undo_activity(self):
        """undo an action"""
        user = self.user if hasattr(self, "user") else self.user_subject
        return activitypub.Undo(
            id="%s#undo" % self.remote_id,
            actor=user.remote_id,
            object=self,
        ).serialize()


def generate_activity(obj):
    """go through the fields on an object"""
    activity = {}
    for field in obj.activity_fields:
        field.set_activity_from_field(activity, obj)

    if hasattr(obj, "serialize_reverse_fields"):
        # for example, editions of a work
        for (
            model_field_name,
            activity_field_name,
            sort_field,
        ) in obj.serialize_reverse_fields:
            related_field = getattr(obj, model_field_name)
            activity[activity_field_name] = unfurl_related_field(
                related_field, sort_field=sort_field
            )

    if not activity.get("id"):
        activity["id"] = obj.get_remote_id()
    return activity


def unfurl_related_field(related_field, sort_field=None):
    """load reverse lookups (like public key owner or Status attachment"""
    if sort_field and hasattr(related_field, "all"):
        return [
            unfurl_related_field(i) for i in related_field.order_by(sort_field).all()
        ]
    if related_field.reverse_unfurl:
        # if it's a one-to-one (key pair)
        if hasattr(related_field, "field_to_activity"):
            return related_field.field_to_activity()
        # if it's one-to-many (attachments)
        return related_field.to_activity()
    return related_field.remote_id


@app.task
def broadcast_task(sender_id, activity, recipients):
    """the celery task for broadcast"""
    user_model = apps.get_model("bookwyrm.User", require_ready=True)
    sender = user_model.objects.get(id=sender_id)
    for recipient in recipients:
        try:
            sign_and_send(sender, activity, recipient)
        except (HTTPError, SSLError, requests.exceptions.ConnectionError):
            pass


def sign_and_send(sender, data, destination):
    """crpyto whatever and http junk"""
    now = http_date()

    if not sender.key_pair.private_key:
        # this shouldn't happen. it would be bad if it happened.
        raise ValueError("No private key found for sender")

    digest = make_digest(data)

    response = requests.post(
        destination,
        data=data,
        headers={
            "Date": now,
            "Digest": digest,
            "Signature": make_signature(sender, destination, now, digest),
            "Content-Type": "application/activity+json; charset=utf-8",
            "User-Agent": USER_AGENT,
        },
    )
    if not response.ok:
        response.raise_for_status()
    return response


# pylint: disable=unused-argument
def to_ordered_collection_page(
    queryset, remote_id, id_only=False, page=1, pure=False, **kwargs
):
    """serialize and pagiante a queryset"""
    paginated = Paginator(queryset, PAGE_LENGTH)

    activity_page = paginated.get_page(page)
    if id_only:
        items = [s.remote_id for s in activity_page.object_list]
    else:
        items = [s.to_activity(pure=pure) for s in activity_page.object_list]

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = "%s?page=%d" % (remote_id, activity_page.next_page_number())
    if activity_page.has_previous():
        prev_page = "%s?page=%d" % (remote_id, activity_page.previous_page_number())
    return activitypub.OrderedCollectionPage(
        id="%s?page=%s" % (remote_id, page),
        partOf=remote_id,
        orderedItems=items,
        next=next_page,
        prev=prev_page,
    )
