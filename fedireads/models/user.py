''' database schema for user data '''
from urllib.parse import urlparse

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver

from fedireads import activitypub
from fedireads.models.shelf import Shelf
from fedireads.settings import DOMAIN
from fedireads.signatures import create_key_pair
from .base_model import ActivityMapping, ActivitypubMixin, FedireadsModel


class User(ActivitypubMixin, AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.TextField(blank=True, null=True)
    public_key = models.TextField(blank=True, null=True)
    inbox = models.CharField(max_length=255, unique=True)
    shared_inbox = models.CharField(max_length=255, blank=True, null=True)
    federated_server = models.ForeignKey(
        'FederatedServer',
        on_delete=models.PROTECT,
        null=True,
    )
    outbox = models.CharField(max_length=255, unique=True)
    summary = models.TextField(blank=True, null=True)
    local = models.BooleanField(default=True)
    fedireads_user = models.BooleanField(default=True)
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
            # TODO not the right way to get the media type
            media_type = 'image/%s' % url.split('.')[-1]
        else:
            url = '%s/static/images/default_avi.jpg' % DOMAIN
            media_type = 'image/jpeg'
        return activitypub.Image(media_type, url, 'Image')

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

    def to_follow_activity(self, user):
        ''' generate a follow request for this user '''
        return activitypub.Follow(
            id='%s#follow' % self.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        )


class UserRelationship(FedireadsModel):
    ''' many-to-many through table for followers '''
    user_subject = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='%(class)s_user_subject'
    )
    user_object = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='%(class)s_user_object'
    )
    # follow or follow_request for pending TODO: blocking?
    relationship_id = models.CharField(max_length=100)

    class Meta:
        ''' relationships should be unique '''
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['user_subject', 'user_object'],
                name='%(class)s_unique'
            ),
            models.CheckConstraint(
                check=~models.Q(user_subject=models.F('user_object')),
                name='%(class)s_no_self'
            )
        ]

    def get_remote_id(self):
        ''' use shelf identifier in remote_id '''
        base_path = self.user_subject.remote_id
        return '%s#%s/%d' % (base_path, self.status, self.id)


class UserFollows(UserRelationship):
    ''' Following a user '''
    @property
    def status(self):
        return 'follows'

    @classmethod
    def from_request(cls, follow_request):
        ''' converts a follow request into a follow relationship '''
        return cls(
            user_subject=follow_request.user_subject,
            user_object=follow_request.user_object,
            relationship_id=follow_request.relationship_id,
        )


class UserFollowRequest(UserRelationship):
    ''' following a user requires manual or automatic confirmation '''
    @property
    def status(self):
        return 'follow_request'

    def to_accept_activity(self, user):
        ''' generate an Accept for this follow request '''
        return activitypub.Accept(
            id='%s#accepts/follows/' % self.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        )

    def to_reject_activity(self, user):
        ''' generate an Accept for this follow request '''
        return activitypub.Reject(
            id='%s#rejects/follows/' % self.remote_id,
            actor=user.remote_id,
            object=self.to_activity()
        )


class UserBlocks(UserRelationship):
    @property
    def status(self):
        return 'blocks'


class FederatedServer(FedireadsModel):
    ''' store which server's we federate with '''
    server_name = models.CharField(max_length=255, unique=True)
    # federated, blocked, whatever else
    status = models.CharField(max_length=255, default='federated')
    # is it mastodon, fedireads, etc
    application_type = models.CharField(max_length=255, null=True)
    application_version = models.CharField(max_length=255, null=True)


@receiver(models.signals.pre_save, sender=User)
def execute_before_save(sender, instance, *args, **kwargs):
    ''' populate fields for new local users '''
    # this user already exists, no need to poplate fields
    if instance.id:
        return
    if not instance.local:
        # we need to generate a username that uses the domain (webfinger format)
        actor_parts = urlparse(instance.remote_id)
        instance.username = '%s@%s' % (instance.username, actor_parts.netloc)
        return

    # populate fields for local users
    instance.remote_id = 'https://%s/user/%s' % (DOMAIN, instance.username)
    instance.localname = instance.username
    instance.username = '%s@%s' % (instance.username, DOMAIN)
    instance.actor = instance.remote_id
    instance.inbox = '%s/inbox' % instance.remote_id
    instance.shared_inbox = 'https://%s/inbox' % DOMAIN
    instance.outbox = '%s/outbox' % instance.remote_id
    if not instance.private_key:
        instance.private_key, instance.public_key = create_key_pair()


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
