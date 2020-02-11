''' database schema for user data '''
from Crypto import Random
from Crypto.PublicKey import RSA
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver

from fedireads.models import Shelf
from fedireads.settings import DOMAIN


class User(AbstractUser):
    ''' a user who wants to read books '''
    private_key = models.TextField(blank=True, null=True)
    public_key = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)
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
    localname = models.CharField(
        max_length=255,
        null=True,
        unique=True
    )
    # name is your display name, which you can change at will
    name = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    followers = models.ManyToManyField('self', symmetrical=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


class FederatedServer(models.Model):
    ''' store which server's we federate with '''
    server_name = models.CharField(max_length=255, unique=True)
    shared_inbox = models.CharField(max_length=255, unique=True)
    # federated, blocked, whatever else
    status = models.CharField(max_length=255, default='federated')
    # is it mastodon, fedireads, etc
    application_type = models.CharField(max_length=255, null=True)


@receiver(models.signals.pre_save, sender=User)
def execute_before_save(sender, instance, *args, **kwargs):
    ''' create shelves for new users '''
    # this user already exists, no need to poplate fields
    if instance.id or not instance.local:
        return

    # populate fields for local users
    instance.localname = instance.username
    instance.username = '%s@%s' % (instance.username, DOMAIN)
    instance.actor = 'https://%s/user/%s' % (DOMAIN, instance.localname)
    instance.inbox = 'https://%s/user/%s/inbox' % (DOMAIN, instance.localname)
    instance.shared_inbox = 'https://%s/inbox' % DOMAIN
    instance.outbox = 'https://%s/user/%s/outbox' % (DOMAIN, instance.localname)
    if not instance.private_key:
        random_generator = Random.new().read
        key = RSA.generate(1024, random_generator)
        instance.private_key = key.export_key().decode('utf8')
        instance.public_key = key.publickey().export_key().decode('utf8')


@receiver(models.signals.post_save, sender=User)
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' create shelves for new users '''
    # TODO: how are remote users handled? what if they aren't readers?
    if not instance.local or not created:
        return

    shelves = [{
        'name': 'To Read',
        'type': 'to-read',
    }, {
        'name': 'Currently Reading',
        'type': 'reading',
    }, {
        'name': 'Read',
        'type': 'read',
    }]

    for shelf in shelves:
        Shelf(
            name=shelf['name'],
            shelf_type=shelf['type'],
            user=instance,
            editable=False
        ).save()

