""" database schema for user data """
import datetime
from importlib import import_module
import re
import zoneinfo
from typing import Optional, Iterable
from urllib.parse import urlparse
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField as DjangoArrayField
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.dispatch import receiver
from django.db import models, transaction, IntegrityError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

from bookwyrm import activitypub
from bookwyrm.connectors import get_data, ConnectorException
from bookwyrm.models.shelf import Shelf
from bookwyrm.models.status import Status
from bookwyrm.preview_images import generate_user_preview_image_task
from bookwyrm.settings import BASE_URL, ENABLE_PREVIEW_IMAGES, LANGUAGES
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app, MISC
from bookwyrm.utils import regex
from bookwyrm.utils.db import add_update_fields
from .activitypub_mixin import OrderedCollectionPageMixin, ActivitypubMixin
from .base_model import BookWyrmModel, DeactivationReason, new_access_code
from .federated_server import FederatedServer
from . import fields

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

FeedFilterChoices = [
    ("review", _("Reviews")),
    ("comment", _("Comments")),
    ("quotation", _("Quotations")),
    ("everything", _("Everything else")),
]


def get_feed_filter_choices():
    """return a list of filter choice keys"""
    return [f[0] for f in FeedFilterChoices]


# pylint: disable=too-many-public-methods
class User(OrderedCollectionPageMixin, AbstractUser):
    """a user who wants to read books"""

    username = fields.UsernameField()
    email = models.EmailField(unique=True, null=True)
    is_deleted = models.BooleanField(default=False)

    key_pair = fields.OneToOneField(
        "KeyPair",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        activitypub_field="publicKey",
        related_name="owner",
    )
    inbox = fields.RemoteIdField(unique=True)
    shared_inbox = fields.RemoteIdField(
        activitypub_field="sharedInbox",
        activitypub_wrapper="endpoints",
        deduplication_field=False,
        null=True,
    )
    federated_server = models.ForeignKey(
        "FederatedServer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    outbox = fields.RemoteIdField(unique=True, null=True)
    summary = fields.HtmlField(null=True, blank=True)
    local = models.BooleanField(default=False)
    bookwyrm_user = fields.BooleanField(default=True)
    localname = models.CharField(
        max_length=255,
        null=True,
        unique=True,
        validators=[fields.validate_localname],
        db_collation="case_insensitive",
    )
    # name is your display name, which you can change at will
    name = fields.CharField(max_length=100, null=True, blank=True)
    avatar = fields.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        activitypub_field="icon",
        alt_field="alt_text",
    )
    preview_image = models.ImageField(
        upload_to="previews/avatars/", blank=True, null=True
    )
    followers_url = fields.CharField(max_length=255, activitypub_field="followers")
    followers = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="UserFollows",
        through_fields=("user_object", "user_subject"),
        related_name="following",
    )
    follow_requests = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="UserFollowRequest",
        through_fields=("user_subject", "user_object"),
        related_name="follower_requests",
    )
    blocks = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="UserBlocks",
        through_fields=("user_subject", "user_object"),
        related_name="blocked_by",
    )
    saved_lists = models.ManyToManyField(
        "List", symmetrical=False, related_name="saved_lists", blank=True
    )
    favorites = models.ManyToManyField(
        "Status",
        symmetrical=False,
        through="Favorite",
        through_fields=("user", "status"),
        related_name="favorite_statuses",
    )
    default_post_privacy = models.CharField(
        max_length=255, default="public", choices=fields.PrivacyLevels
    )
    remote_id = fields.RemoteIdField(null=True, unique=True, activitypub_field="id")
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    last_active_date = models.DateTimeField(default=timezone.now)
    manually_approves_followers = fields.BooleanField(default=False)
    theme = models.ForeignKey("Theme", null=True, blank=True, on_delete=models.SET_NULL)
    hide_follows = fields.BooleanField(default=False)

    # migration fields
    moved_to = fields.RemoteIdField(
        null=True, unique=False, activitypub_field="movedTo", deduplication_field=False
    )
    also_known_as = fields.ManyToManyField(
        "self",
        symmetrical=False,
        unique=False,
        activitypub_field="alsoKnownAs",
        deduplication_field=False,
    )

    # options to turn features on and off
    show_goal = models.BooleanField(default=True)
    show_suggested_users = models.BooleanField(default=True)
    discoverable = fields.BooleanField(default=False)
    show_guided_tour = models.BooleanField(default=True)
    show_ratings = models.BooleanField(default=True)

    # feed options
    feed_status_types = DjangoArrayField(
        models.CharField(max_length=10, blank=False, choices=FeedFilterChoices),
        size=8,
        default=get_feed_filter_choices,
    )
    # annual summary keys
    summary_keys = models.JSONField(null=True)

    preferred_timezone = models.CharField(
        choices=[(str(tz), str(tz)) for tz in sorted(zoneinfo.available_timezones())],
        default=str(datetime.timezone.utc),
        max_length=255,
    )
    preferred_language = models.CharField(
        choices=LANGUAGES,
        null=True,
        blank=True,
        max_length=255,
    )
    deactivation_reason = models.CharField(
        max_length=255, choices=DeactivationReason, null=True, blank=True
    )
    deactivation_date = models.DateTimeField(null=True, blank=True)
    allow_reactivation = models.BooleanField(default=False)
    confirmation_code = models.CharField(max_length=32, default=new_access_code)

    name_field = "username"
    property_fields = [("following_link", "following")]
    field_tracker = FieldTracker(fields=["name", "avatar"])

    # two factor authentication
    two_factor_auth = models.BooleanField(default=None, blank=True, null=True)
    otp_secret = models.CharField(max_length=32, default=None, blank=True, null=True)
    hotp_secret = models.CharField(max_length=32, default=None, blank=True, null=True)
    hotp_count = models.IntegerField(default=0, blank=True, null=True)

    class Meta(AbstractUser.Meta):
        """indexes"""

        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["is_active", "local"]),
        ]

    @property
    def active_follower_requests(self):
        """Follow requests from active users"""
        return self.follower_requests.filter(is_active=True)

    @property
    def confirmation_link(self):
        """helper for generating confirmation links"""
        return f"{BASE_URL}/confirm-email/{self.confirmation_code}"

    @property
    def following_link(self):
        """just how to find out the following info"""
        return f"{self.remote_id}/following"

    @property
    def alt_text(self):
        """alt text with username"""
        # pylint: disable=consider-using-f-string
        return "avatar for {:s}".format(self.localname or self.username)

    @property
    def display_name(self):
        """show the cleanest version of the user's name possible"""
        if self.name and self.name != "":
            return self.name
        return self.localname or self.username

    @property
    def deleted(self):
        """for consistent naming"""
        return not self.is_active

    @property
    def unread_notification_count(self):
        """count of notifications, for the templates"""
        return self.notification_set.filter(read=False).count()

    @property
    def has_unread_mentions(self):
        """whether any of the unread notifications are conversations"""
        return self.notification_set.filter(
            read=False,
            notification_type__in=["REPLY", "MENTION", "TAG", "REPORT"],
        ).exists()

    activity_serializer = activitypub.Person

    @classmethod
    def viewer_aware_objects(cls, viewer):
        """the user queryset filtered for the context of the logged in user"""
        queryset = cls.objects.filter(is_active=True)
        if viewer and viewer.is_authenticated:
            queryset = queryset.exclude(blocks=viewer)
        return queryset

    @classmethod
    def admins(cls):
        """Get a queryset of the admins for this instance"""
        return cls.objects.filter(
            models.Q(groups__name__in=["moderator", "admin"])
            | models.Q(is_superuser=True),
            is_active=True,
        ).distinct()

    def update_active_date(self):
        """this user is here! they are doing things!"""
        self.last_active_date = timezone.now()
        self.save(broadcast=False, update_fields=["last_active_date"])

    def to_outbox(self, filter_type=None, **kwargs):
        """an ordered collection of statuses"""
        if filter_type:
            filter_class = apps.get_model(f"bookwyrm.{filter_type}", require_ready=True)
            if not issubclass(filter_class, Status):
                raise TypeError(
                    "filter_status_class must be a subclass of models.Status"
                )
            queryset = filter_class.objects
        else:
            queryset = Status.objects

        queryset = (
            queryset.filter(
                user=self,
                deleted=False,
                privacy__in=["public", "unlisted"],
            )
            .select_subclasses()
            .order_by("-published_date")
        )
        return self.to_ordered_collection(
            queryset, collection_only=True, remote_id=self.outbox, **kwargs
        ).serialize()

    def to_following_activity(self, **kwargs):
        """activitypub following list"""
        remote_id = f"{self.remote_id}/following"
        return self.to_ordered_collection(
            self.following.order_by("-updated_date").all(),
            remote_id=remote_id,
            collection_only=True,
            id_only=True,
            **kwargs,
        ).serialize()

    def to_followers_activity(self, **kwargs):
        """activitypub followers list"""
        remote_id = self.followers_url
        return self.to_ordered_collection(
            self.followers.order_by("-updated_date").all(),
            remote_id=remote_id,
            collection_only=True,
            id_only=True,
            **kwargs,
        ).serialize()

    def to_activity(self, **kwargs):
        """override default AP serializer to add context object
        idk if this is the best way to go about this"""
        if not self.is_active:
            return self.remote_id

        activity_object = super().to_activity(**kwargs)
        activity_object["@context"] = [
            "https://www.w3.org/ns/activitystreams",
            "https://w3id.org/security/v1",
            {
                "manuallyApprovesFollowers": "as:manuallyApprovesFollowers",
                "Hashtag": "as:Hashtag",
                "schema": "http://schema.org#",
                "PropertyValue": "schema:PropertyValue",
                "value": "schema:value",
                "alsoKnownAs": {"@id": "as:alsoKnownAs", "@type": "@id"},
                "movedTo": {"@id": "as:movedTo", "@type": "@id"},
            },
        ]
        return activity_object

    def save(self, *args, update_fields: Optional[Iterable[str]] = None, **kwargs):
        """populate fields for new local users"""
        created = not bool(self.id)
        if not self.local and not re.match(regex.FULL_USERNAME, self.username):
            # generate a username that uses the domain (webfinger format)
            actor_parts = urlparse(self.remote_id)
            self.username = f"{self.username}@{actor_parts.hostname}"
            update_fields = add_update_fields(update_fields, "username")

        # this user already exists, no need to populate fields
        if not created:
            if self.is_active:
                self.deactivation_date = None
            elif not self.deactivation_date:
                self.deactivation_date = timezone.now()

            super().save(*args, update_fields=update_fields, **kwargs)
            return

        # this is a new remote user, we need to set their remote server field
        if not self.local:
            super().save(*args, update_fields=update_fields, **kwargs)
            transaction.on_commit(lambda: set_remote_server(self.id))
            return

        with transaction.atomic():
            # populate fields for local users
            self.remote_id = f"{BASE_URL}/user/{self.localname}"
            self.followers_url = f"{self.remote_id}/followers"
            self.inbox = f"{self.remote_id}/inbox"
            self.shared_inbox = f"{BASE_URL}/inbox"
            self.outbox = f"{self.remote_id}/outbox"

            update_fields = add_update_fields(
                update_fields,
                "remote_id",
                "followers_url",
                "inbox",
                "shared_inbox",
                "outbox",
            )

            # an id needs to be set before we can proceed with related models
            super().save(*args, update_fields=update_fields, **kwargs)

            # make users editors by default
            try:
                group = (
                    apps.get_model("bookwyrm.SiteSettings")
                    .objects.get()
                    .default_user_auth_group
                )
                if group:
                    self.groups.add(group)
            except ObjectDoesNotExist:
                # this should only happen in tests
                pass

            # create keys and shelves for new local users
            self.key_pair = KeyPair.objects.create(
                remote_id=f"{self.remote_id}/#main-key"
            )
            self.save(broadcast=False, update_fields=["key_pair"])

            self.create_shelves()

    def delete(self, *args, **kwargs):
        """We don't actually delete the database entry"""
        self.is_active = False
        self.allow_reactivation = False
        self.is_deleted = True

        self.erase_user_data()
        self.erase_user_statuses()

        # skip the logic in this class's save()
        super().save(
            *args,
            **kwargs,
        )

    def erase_user_data(self):
        """Wipe a user's custom data"""
        if not self.is_deleted:
            raise IntegrityError(
                "Trying to erase user data on user that is not deleted"
            )

        # mangle email address
        self.email = f"{uuid4()}@deleted.user"

        # erase data fields
        self.avatar = ""
        self.preview_image = ""
        self.summary = None
        self.name = None
        self.favorites.set([])

    def erase_user_statuses(self, broadcast=True):
        """Wipe the data on all the user's statuses"""
        if not self.is_deleted:
            raise IntegrityError(
                "Trying to erase user data on user that is not deleted"
            )

        for status in self.status_set.all():
            status.delete(broadcast=broadcast)

    def deactivate(self):
        """Disable the user but allow them to reactivate"""
        self.is_active = False
        self.deactivation_reason = "self_deactivation"
        self.allow_reactivation = True
        super().save(broadcast=False)

    def reactivate(self):
        """Now you want to come back, huh?"""
        if not self.allow_reactivation:
            return
        self.is_active = True
        self.deactivation_reason = None
        self.allow_reactivation = False
        super().save(
            broadcast=False,
            update_fields=["deactivation_reason", "is_active", "allow_reactivation"],
        )

    @property
    def local_path(self):
        """this model doesn't inherit bookwyrm model, so here we are"""
        # pylint: disable=consider-using-f-string
        return "/user/{:s}".format(self.localname or self.username)

    def create_shelves(self):
        """default shelves for a new user"""
        shelves = [
            {
                "name": "To Read",
                "identifier": "to-read",
            },
            {
                "name": "Currently Reading",
                "identifier": "reading",
            },
            {
                "name": "Read",
                "identifier": "read",
            },
            {
                "name": "Stopped Reading",
                "identifier": "stopped-reading",
            },
        ]

        for shelf in shelves:
            Shelf(
                name=shelf["name"],
                identifier=shelf["identifier"],
                user=self,
                editable=False,
            ).save(broadcast=False)

    def raise_not_editable(self, viewer):
        """Who can edit the user object?"""
        if self == viewer or viewer.has_perm("bookwyrm.moderate_user"):
            return
        raise PermissionDenied()

    def refresh_user_sessions(self):
        """Check sessions still exist
        We delete them on logout but not when sessions expire"""

        cache_session = SessionStore()
        for sess in self.sessions.all():
            if not cache_session.exists(session_key=sess.session_key):
                sess.delete()


class KeyPair(ActivitypubMixin, BookWyrmModel):
    """public and private keys for a user"""

    private_key = models.TextField(blank=True, null=True)
    public_key = fields.TextField(
        blank=True, null=True, activitypub_field="publicKeyPem"
    )

    activity_serializer = activitypub.PublicKey
    serialize_reverse_fields = [("owner", "owner", "id")]

    class Meta:
        """indexes"""

        indexes = [
            models.Index(fields=["remote_id"]),
        ]

    def get_remote_id(self):
        # self.owner is set by the OneToOneField on User
        return f"{self.owner.remote_id}/#main-key"

    def save(self, *args, update_fields: Optional[Iterable[str]] = None, **kwargs):
        """create a key pair"""
        # no broadcasting happening here
        if "broadcast" in kwargs:
            del kwargs["broadcast"]

        if not self.public_key:
            self.private_key, self.public_key = create_key_pair()
            update_fields = add_update_fields(
                update_fields, "private_key", "public_key"
            )

        super().save(*args, update_fields=update_fields, **kwargs)


@app.task(queue=MISC)
def erase_user_data(user_id):
    """Erase any custom data about this user asynchronously
    This is for deleted historical user data that pre-dates data
    being cleared automatically"""
    user = User.objects.get(id=user_id)
    user.erase_user_data()
    user.save(
        broadcast=False,
        update_fields=["email", "avatar", "preview_image", "summary", "name"],
    )
    user.erase_user_statuses(broadcast=False)


@app.task(queue=MISC)
def set_remote_server(user_id, allow_external_connections=False):
    """figure out the user's remote server in the background"""
    user = User.objects.get(id=user_id)
    actor_parts = urlparse(user.remote_id)
    federated_server = get_or_create_remote_server(
        actor_parts.hostname, allow_external_connections=allow_external_connections
    )
    # if we were unable to find the server, we need to create a new entry for it
    if not federated_server:
        # and to do that, we will call this function asynchronously.
        if not allow_external_connections:
            set_remote_server.delay(user_id, allow_external_connections=True)
        return

    user.federated_server = federated_server
    user.save(broadcast=False, update_fields=["federated_server"])
    if user.bookwyrm_user and user.outbox:
        get_remote_reviews.delay(user.outbox)


def get_or_create_remote_server(
    domain, allow_external_connections=False, refresh=False
):
    """get info on a remote server"""
    server = FederatedServer()
    try:
        server = FederatedServer.objects.get(server_name=domain)
        if not refresh:
            return server
    except FederatedServer.DoesNotExist:
        pass

    if not allow_external_connections:
        return None

    try:
        data = get_data(f"https://{domain}/.well-known/nodeinfo")
        try:
            nodeinfo_url = data.get("links")[0].get("href")
        except (TypeError, KeyError):
            raise ConnectorException()

        data = get_data(nodeinfo_url)
        application_type = data.get("software", {}).get("name")
        application_version = data.get("software", {}).get("version")
    except ConnectorException:
        if server.id:
            return server
        application_type = application_version = None

    server.server_name = domain
    server.application_type = application_type
    server.application_version = application_version

    server.save()
    return server


@app.task(queue=MISC)
def get_remote_reviews(outbox):
    """ingest reviews by a new remote bookwyrm user"""
    outbox_page = outbox + "?page=true&type=Review"
    data = get_data(outbox_page)

    # TODO: pagination?
    for activity in data["orderedItems"]:
        if not activity["type"] == "Review":
            continue
        activitypub.Review(**activity).to_model()


# pylint: disable=unused-argument
@receiver(models.signals.post_save, sender=User)
def preview_image(instance, *args, **kwargs):
    """create preview images when user is updated"""
    if not ENABLE_PREVIEW_IMAGES:
        return

    # don't call the task for remote users
    if not instance.local:
        return

    changed_fields = instance.field_tracker.changed()

    if len(changed_fields) > 0:
        generate_user_preview_image_task.delay(instance.id)
