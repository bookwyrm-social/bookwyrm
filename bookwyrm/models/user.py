''' database schema for user data '''
from urllib.parse import urlparse
import requests

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver

from bookwyrm import activitypub
from bookwyrm.models.shelf import Shelf
from bookwyrm.models.status import Status, Review
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app
from .base_model import ActivityMapping, OrderedCollectionPageMixin
from .federated_server import FederatedServer


class User(OrderedCollectionPageMixin, AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.TextField(blank=True, null=True)
    public_key = models.TextField(blank=True, null=True)
    inbox = models.CharField(max_length=255, unique=True)
    shared_inbox = models.CharField(max_length=255, blank=True, null=True)
    federated_server = models.ForeignKey(
        'FederatedServer',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    outbox = models.CharField(max_length=255, unique=True)
    summary = models.TextField(blank=True, null=True)
    local = models.BooleanField(default=True)
    bookwyrm_user = models.BooleanField(default=True)
    localname = models.CharField(
        max_length=255,
        null=True,
        unique=True
    )
    # name is your display name, which you can change at will
    name = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    following = models.ManyToManyField(
        'self',
        symmetrical=False,
        through='UserFollows',
        through_fields=('user_subject', 'user_object'),
        related_name='followers'
    )
    follow_requests = models.ManyToManyField(
        'self',
        symmetrical=False,
        through='UserFollowRequest',
        through_fields=('user_subject', 'user_object'),
        related_name='follower_requests'
    )
    blocks = models.ManyToManyField(
        'self',
        symmetrical=False,
        through='UserBlocks',
        through_fields=('user_subject', 'user_object'),
        related_name='blocked_by'
    )
    favorites = models.ManyToManyField(
        'Status',
        symmetrical=False,
        through='Favorite',
        through_fields=('user', 'status'),
        related_name='favorite_statuses'
    )
    remote_id = models.CharField(max_length=255, null=True, unique=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    last_active_date = models.DateTimeField(auto_now=True)
    manually_approves_followers = models.BooleanField(default=False)

    # ---- activitypub serialization settings for this model ----- #
    @property
    def ap_followers(self):
        ''' generates url for activitypub followers page '''
        return '%s/followers' % self.remote_id

    @property
    def ap_public_key(self):
        ''' format the public key block for activitypub '''
        return activitypub.PublicKey(**{
            'id': '%s/#main-key' % self.remote_id,
            'owner': self.remote_id,
            'publicKeyPem': self.public_key,
        })

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping(
            'preferredUsername',
            'username',
            activity_formatter=lambda x: x.split('@')[0]
        ),
        ActivityMapping('name', 'name'),
        ActivityMapping('bookwyrmUser', 'bookwyrm_user'),
        ActivityMapping('inbox', 'inbox'),
        ActivityMapping('outbox', 'outbox'),
        ActivityMapping('followers', 'ap_followers'),
        ActivityMapping('summary', 'summary'),
        ActivityMapping(
            'publicKey',
            'public_key',
            model_formatter=lambda x: x.get('publicKeyPem')
        ),
        ActivityMapping('publicKey', 'ap_public_key'),
        ActivityMapping(
            'endpoints',
            'shared_inbox',
            activity_formatter=lambda x: {'sharedInbox': x},
            model_formatter=lambda x: x.get('sharedInbox')
        ),
        ActivityMapping('icon', 'avatar'),
        ActivityMapping(
            'manuallyApprovesFollowers',
            'manually_approves_followers'
        ),
        # this field isn't in the activity but should always be false
        ActivityMapping(None, 'local', model_formatter=lambda x: False),
    ]
    activity_serializer = activitypub.Person

    def to_outbox(self, **kwargs):
        ''' an ordered collection of statuses '''
        queryset = Status.objects.filter(
            user=self,
            deleted=False,
        ).select_subclasses()
        return self.to_ordered_collection(queryset, \
                remote_id=self.outbox, **kwargs)

    def to_following_activity(self, **kwargs):
        ''' activitypub following list '''
        remote_id = '%s/following' % self.remote_id
        return self.to_ordered_collection(self.following, \
                remote_id=remote_id, id_only=True, **kwargs)

    def to_followers_activity(self, **kwargs):
        ''' activitypub followers list '''
        remote_id = '%s/followers' % self.remote_id
        return self.to_ordered_collection(self.followers, \
                remote_id=remote_id, id_only=True, **kwargs)

    def to_activity(self, pure=False):
        ''' override default AP serializer to add context object
            idk if this is the best way to go about this '''
        activity_object = super().to_activity()
        activity_object['@context'] = [
            'https://www.w3.org/ns/activitystreams',
            'https://w3id.org/security/v1',
            {
                'manuallyApprovesFollowers': 'as:manuallyApprovesFollowers',
                'schema': 'http://schema.org#',
                'PropertyValue': 'schema:PropertyValue',
                'value': 'schema:value',
            }
        ]
        return activity_object


    def save(self, *args, **kwargs):
        ''' populate fields for new local users '''
        # this user already exists, no need to populate fields
        if self.id:
            return super().save(*args, **kwargs)

        if not self.local:
            # generate a username that uses the domain (webfinger format)
            actor_parts = urlparse(self.remote_id)
            self.username = '%s@%s' % (self.username, actor_parts.netloc)
            return super().save(*args, **kwargs)

        # populate fields for local users
        self.remote_id = 'https://%s/user/%s' % (DOMAIN, self.username)
        self.localname = self.username
        self.username = '%s@%s' % (self.username, DOMAIN)
        self.actor = self.remote_id
        self.inbox = '%s/inbox' % self.remote_id
        self.shared_inbox = 'https://%s/inbox' % DOMAIN
        self.outbox = '%s/outbox' % self.remote_id
        if not self.private_key:
            self.private_key, self.public_key = create_key_pair()

        return super().save(*args, **kwargs)


@receiver(models.signals.post_save, sender=User)
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' create shelves for new users '''
    if not created:
        return

    if not instance.local:
        actor_parts = urlparse(instance.remote_id)
        instance.federated_server = \
            get_or_create_remote_server(actor_parts.netloc)
        instance.save()
        if instance.bookwyrm_user:
            get_remote_reviews.delay(instance.outbox)
        return

    shelves = [{
        'name': 'To Read',
        'identifier': 'to-read',
    }, {
        'name': 'Currently Reading',
        'identifier': 'reading',
    }, {
        'name': 'Read',
        'identifier': 'read',
    }]

    for shelf in shelves:
        Shelf(
            name=shelf['name'],
            identifier=shelf['identifier'],
            user=instance,
            editable=False
        ).save()


def get_or_create_remote_server(domain):
    ''' get info on a remote server '''
    try:
        return FederatedServer.objects.get(
            server_name=domain
        )
    except FederatedServer.DoesNotExist:
        pass

    response = requests.get(
        'https://%s/.well-known/nodeinfo' % domain,
        headers={'Accept': 'application/activity+json'}
    )

    if response.status_code != 200:
        return None

    data = response.json()
    try:
        nodeinfo_url = data.get('links')[0].get('href')
    except (TypeError, KeyError):
        return None

    response = requests.get(
        nodeinfo_url,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()

    server = FederatedServer.objects.create(
        server_name=domain,
        application_type=data['software']['name'],
        application_version=data['software']['version'],
    )
    return server


@app.task
def get_remote_reviews(outbox):
    ''' ingest reviews by a new remote bookwyrm user '''
    outbox_page = outbox + '?page=true'
    response = requests.get(
        outbox_page,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()
    # TODO: pagination?
    for activity in data['orderedItems']:
        if not activity['type'] == 'Review':
            continue
        activitypub.Review(**activity).to_model(Review)
