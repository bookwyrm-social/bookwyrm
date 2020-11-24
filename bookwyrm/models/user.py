''' database schema for user data '''
from urllib.parse import urlparse

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver

from bookwyrm import activitypub
from bookwyrm.models.shelf import Shelf
from bookwyrm.models.status import Status
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import create_key_pair
from .base_model import OrderedCollectionPageMixin, ActivityMapping, PrivacyLevels

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
    default_post_privacy = models.CharField(
        max_length=255,
        default='public',
        choices=PrivacyLevels.choices
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
    def ap_icon(self):
        ''' send default icon if one isn't set '''
        if self.avatar:
            url = self.avatar.url
        else:
            url = '/static/images/default_avi.jpg'
        url = 'https://%s%s' % (DOMAIN, url)
        return activitypub.Image(url=url)

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
        ActivityMapping('icon', 'ap_icon'),
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
    if not instance.local or not created:
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
