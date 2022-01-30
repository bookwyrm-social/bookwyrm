""" database schema for user data """
import re
from urllib.parse import urlparse

from django.apps import apps
from django.contrib.auth.models import AbstractUser, Group
from django.contrib.postgres.fields import ArrayField, CICharField
from django.core.validators import MinValueValidator
from django.dispatch import receiver
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker
import pytz

from bookwyrm import activitypub
from bookwyrm.connectors import get_data, ConnectorException
from bookwyrm.models.shelf import Shelf
from bookwyrm.models.status import Status, Review
from bookwyrm.preview_images import generate_user_preview_image_task
from bookwyrm.settings import DOMAIN, ENABLE_PREVIEW_IMAGES, USE_HTTPS, LANGUAGES
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app
from bookwyrm.utils import regex
from .activitypub_mixin import OrderedCollectionPageMixin, ActivitypubMixin
from .base_model import BookWyrmModel, DeactivationReason, new_access_code
from .federated_server import FederatedServer
from . import fields, Review


FeedFilterChoices = [
    ("review", _("Reviews")),
    ("comment", _("Comments")),
    ("quotation", _("Quotations")),
    ("everything", _("Everything else")),
]


def get_feed_filter_choices():
    """return a list of filter choice keys"""
    return [f[0] for f in FeedFilterChoices]


def site_link():
    """helper for generating links to the site"""
    protocol = "https" if USE_HTTPS else "http"
    return f"{protocol}://{DOMAIN}"


class User(OrderedCollectionPageMixin, AbstractUser):
    """a user who wants to read books"""

    username = fields.UsernameField()
    email = models.EmailField(unique=True, null=True)

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
    localname = CICharField(
        max_length=255,
        null=True,
        unique=True,
        validators=[fields.validate_localname],
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

    # options to turn features on and off
    show_goal = models.BooleanField(default=True)
    show_suggested_users = models.BooleanField(default=True)
    discoverable = fields.BooleanField(default=False)

    # feed options
    feed_status_types = ArrayField(
        models.CharField(max_length=10, blank=False, choices=FeedFilterChoices),
        size=8,
        default=get_feed_filter_choices,
    )
    # annual summary keys
    summary_keys = models.JSONField(null=True)

    preferred_timezone = models.CharField(
        choices=[(str(tz), str(tz)) for tz in pytz.all_timezones],
        default=str(pytz.utc),
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
    confirmation_code = models.CharField(max_length=32, default=new_access_code)

    name_field = "username"
    property_fields = [("following_link", "following")]
    field_tracker = FieldTracker(fields=["name", "avatar"])

    @property
    def confirmation_link(self):
        """helper for generating confirmation links"""
        link = site_link()
        return f"{link}/confirm-email/{self.confirmation_code}"

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
            id_only=True,
            **kwargs,
        )

    def to_followers_activity(self, **kwargs):
        """activitypub followers list"""
        remote_id = self.followers_url
        return self.to_ordered_collection(
            self.followers.order_by("-updated_date").all(),
            remote_id=remote_id,
            id_only=True,
            **kwargs,
        )

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
                "schema": "http://schema.org#",
                "PropertyValue": "schema:PropertyValue",
                "value": "schema:value",
            },
        ]
        return activity_object

    def save(self, *args, **kwargs):
        """populate fields for new local users"""
        created = not bool(self.id)
        if not self.local and not re.match(regex.FULL_USERNAME, self.username):
            # generate a username that uses the domain (webfinger format)
            actor_parts = urlparse(self.remote_id)
            self.username = f"{self.username}@{actor_parts.netloc}"

        # this user already exists, no need to populate fields
        if not created:
            if self.is_active:
                self.deactivation_date = None
            elif not self.deactivation_date:
                self.deactivation_date = timezone.now()

            super().save(*args, **kwargs)
            return

        # this is a new remote user, we need to set their remote server field
        if not self.local:
            super().save(*args, **kwargs)
            transaction.on_commit(lambda: set_remote_server.delay(self.id))
            return

        with transaction.atomic():
            # populate fields for local users
            link = site_link()
            self.remote_id = f"{link}/user/{self.localname}"
            self.followers_url = f"{self.remote_id}/followers"
            self.inbox = f"{self.remote_id}/inbox"
            self.shared_inbox = f"{link}/inbox"
            self.outbox = f"{self.remote_id}/outbox"

            # an id needs to be set before we can proceed with related models
            super().save(*args, **kwargs)

            # make users editors by default
            try:
                self.groups.add(Group.objects.get(name="editor"))
            except Group.DoesNotExist:
                # this should only happen in tests
                pass

            # create keys and shelves for new local users
            self.key_pair = KeyPair.objects.create(
                remote_id=f"{self.remote_id}/#main-key"
            )
            self.save(broadcast=False, update_fields=["key_pair"])

            self.create_shelves()

    def delete(self, *args, **kwargs):
        """deactivate rather than delete a user"""
        # pylint: disable=attribute-defined-outside-init
        self.is_active = False
        # skip the logic in this class's save()
        super().save(*args, **kwargs)

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
        ]

        for shelf in shelves:
            Shelf(
                name=shelf["name"],
                identifier=shelf["identifier"],
                user=self,
                editable=False,
            ).save(broadcast=False)


class KeyPair(ActivitypubMixin, BookWyrmModel):
    """public and private keys for a user"""

    private_key = models.TextField(blank=True, null=True)
    public_key = fields.TextField(
        blank=True, null=True, activitypub_field="publicKeyPem"
    )

    activity_serializer = activitypub.PublicKey
    serialize_reverse_fields = [("owner", "owner", "id")]

    def get_remote_id(self):
        # self.owner is set by the OneToOneField on User
        return f"{self.owner.remote_id}/#main-key"

    def save(self, *args, **kwargs):
        """create a key pair"""
        # no broadcasting happening here
        if "broadcast" in kwargs:
            del kwargs["broadcast"]
        if not self.public_key:
            self.private_key, self.public_key = create_key_pair()
        return super().save(*args, **kwargs)


def get_current_year():
    """sets default year for annual goal to this year"""
    return timezone.now().year


class AnnualGoal(BookWyrmModel):
    """set a goal for how many books you read in a year"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    goal = models.IntegerField(validators=[MinValueValidator(1)])
    year = models.IntegerField(default=get_current_year)
    privacy = models.CharField(
        max_length=255, default="public", choices=fields.PrivacyLevels
    )

    class Meta:
        """unqiueness constraint"""

        unique_together = ("user", "year")

    def get_remote_id(self):
        """put the year in the path"""
        return f"{self.user.remote_id}/goal/{self.year}"

    @property
    def books(self):
        """the books you've read this year"""
        return (
            self.user.readthrough_set.filter(
                finish_date__year__gte=self.year,
                finish_date__year__lt=self.year + 1,
            )
            .order_by("-finish_date")
            .all()
        )

    @property
    def ratings(self):
        """ratings for books read this year"""
        book_ids = [r.book.id for r in self.books]
        reviews = Review.objects.filter(
            user=self.user,
            book__in=book_ids,
        )
        return {r.book.id: r.rating for r in reviews}

    @property
    def progress(self):
        """how many books you've read this year"""
        count = self.user.readthrough_set.filter(
            finish_date__year__gte=self.year,
            finish_date__year__lt=self.year + 1,
        ).count()
        return {
            "count": count,
            "percent": int(float(count / self.goal) * 100),
        }


@app.task(queue="low_priority")
def set_remote_server(user_id):
    """figure out the user's remote server in the background"""
    user = User.objects.get(id=user_id)
    actor_parts = urlparse(user.remote_id)
    user.federated_server = get_or_create_remote_server(actor_parts.netloc)
    user.save(broadcast=False, update_fields=["federated_server"])
    if user.bookwyrm_user and user.outbox:
        get_remote_reviews.delay(user.outbox)


def get_or_create_remote_server(domain):
    """get info on a remote server"""
    try:
        return FederatedServer.objects.get(server_name=domain)
    except FederatedServer.DoesNotExist:
        pass

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
        application_type = application_version = None

    server = FederatedServer.objects.create(
        server_name=domain,
        application_type=application_type,
        application_version=application_version,
    )
    return server


@app.task(queue="low_priority")
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
    changed_fields = instance.field_tracker.changed()

    if len(changed_fields) > 0:
        generate_user_preview_image_task.delay(instance.id)
