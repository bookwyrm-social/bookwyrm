""" base model with default fields """
import base64
from urllib.parse import urlparse
from Crypto import Random

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Q
from django.dispatch import receiver
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from bookwyrm import activitypub
from bookwyrm.connectors import get_data, ConnectorException
from bookwyrm.settings import DOMAIN, USE_HTTPS
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app
from .activitypub_mixin import ActivitypubMixin
from . import fields


DeactivationReason = [
    ("pending", _("Pending")),
    ("self_deletion", _("Self deletion")),
    ("moderator_suspension", _("Moderator suspension")),
    ("moderator_deletion", _("Moderator deletion")),
    ("domain_block", _("Domain block")),
]


def site_link():
    """helper for generating links to the site"""
    protocol = "https" if USE_HTTPS else "http"
    return f"{protocol}://{DOMAIN}"


def new_access_code():
    """the identifier for a user invite"""
    return base64.b32encode(Random.get_random_bytes(5)).decode("ascii")


class BookWyrmModel(models.Model):
    """shared fields"""

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = fields.RemoteIdField(null=True, activitypub_field="id")

    def get_remote_id(self):
        """generate a url that resolves to the local object"""
        base_path = f"https://{DOMAIN}"
        if hasattr(self, "user"):
            base_path = f"{base_path}{self.user.local_path}"
        model_name = type(self).__name__.lower()
        return f"{base_path}/{model_name}/{self.id}"

    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True

    @property
    def local_path(self):
        """how to link to this object in the local app"""
        return self.get_remote_id().replace(f"https://{DOMAIN}", "")

class ActorModel(BookWyrmModel):
    """ something that posts """
    remote_id = fields.RemoteIdField(null=True, activitypub_field="id", unique=True)
    summary = fields.HtmlField(null=True, blank=True)
    outbox = fields.RemoteIdField(unique=True, null=True)
    key_pair = fields.OneToOneField(
        "KeyPair",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        activitypub_field="publicKey",
        related_name="owner",
    )
    followers = models.ManyToManyField(
        "User",
        symmetrical=False,
        through="UserFollows",
        through_fields=("user_object", "user_subject"),
        related_name="following",
    )
    followers_url = fields.CharField(max_length=255, activitypub_field="followers")
    blocks = models.ManyToManyField(
        "User",
        symmetrical=False,
        through="UserBlocks",
        through_fields=("user_subject", "user_object"),
        related_name="blocked_by",
    )
    federated_server = models.ForeignKey(
        "FederatedServer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    inbox = fields.RemoteIdField(unique=True)
    shared_inbox = fields.RemoteIdField(
        activitypub_field="sharedInbox",
        activitypub_wrapper="endpoints",
        deduplication_field=False,
        null=True,
    )
    local = models.BooleanField(default=False)
    discoverable = fields.BooleanField(default=False)
    default_post_privacy = models.CharField(
        max_length=255, default="public", choices=fields.PrivacyLevels.choices
    )

    property_fields = [("following_link", "following")]

    def save(self, *args, **kwargs):
        """ set fields """
        created = not bool(self.id)
        if not created:
            super().save(*args, **kwargs)
            return

        with transaction.atomic():
            # this is a new remote obj, we need to set their remote server field
            if not self.local:
                super().save(*args, **kwargs)
                transaction.on_commit(lambda: set_remote_server.delay(self.id))
                return

            super().save(*args, **kwargs)

            # create keys and shelves for new local users
            self.key_pair = KeyPair.objects.create(
                remote_id=f"{self.remote_id}/#main-key"
            )
            self.save(broadcast=False, update_fields=["key_pair"])


    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True


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

    def to_activity(self, **kwargs):
        """override default AP serializer to add context object
        idk if this is the best way to go about this"""
        activity_object = super().to_activity(**kwargs)
        del activity_object["@context"]
        del activity_object["type"]
        return activity_object



class ObjectModel(BookWyrmModel):
    """ an object you can interact with in specific, activitypub-compliant ways """
    privacy = fields.PrivacyField()
    user = models.ForeignKey("User", on_delete=models.PROTECT)

    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True

    def raise_visible_to_user(self, viewer):
        """is a user authorized to view an object?"""
        # viewer can't see it if the object's owner blocked them
        if viewer in self.user.blocks.all():
            raise Http404()

        # you can see your own posts and any public or unlisted posts
        if viewer == self.user or self.privacy in ["public", "unlisted"]:
            return

        # you can see the followers only posts of people you follow
        if self.privacy == "followers" and (
            self.user.followers.filter(id=viewer.id).first()
        ):
            return

        # you can see dms you are tagged in
        if hasattr(self, "mention_users"):
            if (
                self.privacy in ["direct", "followers"]
                and self.mention_users.filter(id=viewer.id).first()
            ):

                return

        # you can see groups of which you are a member
        if (
            hasattr(self, "memberships")
            and self.memberships.filter(user=viewer).exists()
        ):
            return

        # you can see objects which have a group of which you are a member
        if hasattr(self, "group"):
            if (
                hasattr(self.group, "memberships")
                and self.group.memberships.filter(user=viewer).exists()
            ):
                return

        raise Http404()

    def raise_not_editable(self, viewer):
        """does this user have permission to edit this object? liable to be overwritten
        by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # generally moderators shouldn't be able to edit other people's stuff
        if self.user == viewer:
            return

        raise PermissionDenied()

    def raise_not_deletable(self, viewer):
        """does this user have permission to delete this object? liable to be
        overwritten by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # but generally moderators can delete other people's stuff
        if self.user == viewer or viewer.has_perm("moderate_post"):
            return

        raise PermissionDenied()

    @classmethod
    def privacy_filter(cls, viewer, privacy_levels=None):
        """filter objects that have "user" and "privacy" fields"""
        queryset = cls.objects
        if hasattr(queryset, "select_subclasses"):
            queryset = queryset.select_subclasses()

        privacy_levels = privacy_levels or ["public", "unlisted", "followers", "direct"]
        # you can't see followers only or direct messages if you're not logged in
        if viewer.is_anonymous:
            privacy_levels = [
                p for p in privacy_levels if not p in ["followers", "direct"]
            ]
        else:
            # exclude blocks from both directions
            queryset = queryset.exclude(
                Q(user__blocked_by=viewer) | Q(user__blocks=viewer)
            )

        # filter to only provided privacy levels
        queryset = queryset.filter(privacy__in=privacy_levels)

        if "followers" in privacy_levels:
            queryset = cls.followers_filter(queryset, viewer)

        # exclude direct messages not intended for the user
        if "direct" in privacy_levels:
            queryset = cls.direct_filter(queryset, viewer)

        return queryset

    @classmethod
    def followers_filter(cls, queryset, viewer):
        """Override-able filter for "followers" privacy level"""
        return queryset.exclude(
            ~Q(  # user isn't following and it isn't their own status
                Q(user__followers=viewer) | Q(user=viewer)
            ),
            privacy="followers",  # and the status is followers only
        )

    @classmethod
    def direct_filter(cls, queryset, viewer):
        """Override-able filter for "direct" privacy level"""
        return queryset.exclude(~Q(user=viewer), privacy="direct")



@receiver(models.signals.post_save)
# pylint: disable=unused-argument
def set_remote_id(sender, instance, created, *args, **kwargs):
    """set the remote_id after save (when the id is available)"""
    if not created or not hasattr(instance, "get_remote_id"):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        try:
            instance.save(broadcast=False)
        except TypeError:
            instance.save()

    if not instance.local:
        return

    if issubclass(instance, ActorModel) and not instance.followers_url:
        link = site_link()
        instance.followers_url = f"{instance.remote_id}/followers"
        instance.inbox = f"{instance.remote_id}/inbox"
        instance.shared_inbox = f"{link}/inbox"
        instance.outbox = f"{instance.remote_id}/outbox"


@app.task(queue="low_priority")
def set_remote_server(model_name, obj_id):
    """figure out the obj's remote server in the background"""
    model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
    obj = model.objects.get(id=obj_id)
    actor_parts = urlparse(obj.remote_id)
    obj.federated_server = get_or_create_remote_server(actor_parts.netloc)
    obj.save(broadcast=False, update_fields=["federated_server"])

    if model_name == "User" and obj.bookwyrm_obj and obj.outbox:
        get_remote_reviews.delay(obj.outbox)


def get_or_create_remote_server(domain):
    """get info on a remote server"""
    model = apps.get_model("bookwyrm.FederatedServer", require_ready=True)
    try:
        return model.objects.get(server_name=domain)
    except model.DoesNotExist:
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

    server = model.objects.create(
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
