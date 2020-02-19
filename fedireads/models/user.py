''' database schema for user data '''
from Crypto import Random
from Crypto.PublicKey import RSA
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver

from fedireads.models import Shelf
from fedireads.settings import DOMAIN
from fedireads.utils.models import FedireadsModel


class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.TextField(blank=True, null=True)
    public_key = models.TextField(blank=True, null=True)
    actor = models.CharField(max_length=255, unique=True)
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
    followers = models.ManyToManyField(
        'self',
        symmetrical=False,
        through='UserRelationship',
        through_fields=('user_subject', 'user_object')
    )

    @property
    def absolute_id(self):
        ''' users are identified by their username, so overriding this prop '''
        model_name = type(self).__name__.lower()
        return 'https://%s/%s/%s' % (DOMAIN, model_name, self.localname)


class UserRelationship(FedireadsModel):
    ''' many-to-many through table for followers '''
    user_subject = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='user_subject'
    )
    user_object = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='user_object'
    )
    # follow or follow_request for pending TODO: blocking?
    status = models.CharField(max_length=100, default='follows', null=True)
    relationship_id = models.CharField(max_length=100)

    @property
    def absolute_id(self):
        ''' use shelf identifier as absolute id '''
        base_path = self.user_subject.absolute_id
        return '%s#%s/%d' % (base_path, self.status, self.id)


class FederatedServer(FedireadsModel):
    ''' store which server's we federate with '''
    server_name = models.CharField(max_length=255, unique=True)
    # federated, blocked, whatever else
    status = models.CharField(max_length=255, default='federated')
    # is it mastodon, fedireads, etc
    application_type = models.CharField(max_length=255, null=True)


@receiver(models.signals.pre_save, sender=User)
def execute_before_save(sender, instance, *args, **kwargs):
    ''' populate fields for new local users '''
    # this user already exists, no need to poplate fields
    if instance.id or not instance.local:
        return

    # populate fields for local users
    instance.localname = instance.username
    instance.username = '%s@%s' % (instance.username, DOMAIN)
    instance.actor = instance.absolute_id
    instance.inbox = '%s/inbox' % instance.absolute_id
    instance.shared_inbox = 'https://%s/inbox' % DOMAIN
    instance.outbox = '%s/outbox' % instance.absolute_id
    if not instance.private_key:
        random_generator = Random.new().read
        key = RSA.generate(1024, random_generator)
        instance.private_key = key.export_key().decode('utf8')
        instance.public_key = key.publickey().export_key().decode('utf8')


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

