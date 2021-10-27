""" base model for actors with default fields """
from urllib.parse import urlparse

from django.apps import apps
from django.db import models, transaction

from bookwyrm import activitypub
from bookwyrm.connectors import get_data, ConnectorException
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from .federated_server import FederatedServer
from . import fields


class ActorModel(BookWyrmModel):
    """something that posts"""

    remote_id = fields.RemoteIdField(null=True, activitypub_field="id", unique=True)
    summary = fields.HtmlField(null=True, blank=True)
    outbox = fields.RemoteIdField(unique=True, null=True)
    followers_url = fields.CharField(max_length=255, activitypub_field="followers")
    federated_server = models.ForeignKey(
        "FederatedServer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    inbox = fields.RemoteIdField(unique=True)
    local = models.BooleanField(default=False)
    discoverable = fields.BooleanField(default=False)
    default_post_privacy = models.CharField(
        max_length=255, default="public", choices=fields.PrivacyLevels.choices
    )
    manually_approves_followers = fields.BooleanField(default=False)
    key_pair = fields.OneToOneField(
        "KeyPair",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        activitypub_field="publicKey",
        related_name="owner",
    )

    property_fields = [("following_link", "following")]

    def save(self, *args, **kwargs):
        """set fields"""
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

            self.followers_url = f"{self.remote_id}/followers"
            self.inbox = f"{self.remote_id}/inbox"
            self.outbox = f"{self.remote_id}/outbox"
            super().save(*args, **kwargs)

            # create keys and shelves for new local users
            self.key_pair = KeyPair.objects.create(
                remote_id=f"{self.remote_id}/#main-key"
            )
            self.save(broadcast=False, update_fields=["key_pair"])

    @classmethod
    def viewer_aware_objects(cls, viewer):
        """the user queryset filtered for the context of the logged in user"""
        queryset = cls.objects.filter(is_active=True)
        if viewer and viewer.is_authenticated:
            queryset = queryset.exclude(blocks=viewer)
        return queryset

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


@app.task(queue="low_priority")
def set_remote_server(user_id):
    """figure out the user's remote server in the background"""
    model = apps.get_model("bookwyrm.User", require_ready=True)
    user = model.objects.get(id=user_id)
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
