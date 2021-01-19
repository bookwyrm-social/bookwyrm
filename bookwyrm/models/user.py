''' database schema for user data '''
import re
from urllib.parse import urlparse

from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver
from django.utils import timezone

from bookwyrm import activitypub
from bookwyrm.connectors import get_data
from bookwyrm.models.shelf import Shelf
from bookwyrm.models.status import Status, Review
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import create_key_pair
from bookwyrm.tasks import app
from bookwyrm.utils import regex
from .base_model import OrderedCollectionPageMixin
from .base_model import ActivitypubMixin, BookWyrmModel
from .federated_server import FederatedServer
from . import fields, Review


class User(OrderedCollectionPageMixin, AbstractUser):
    ''' a user who wants to read books '''
    username = fields.UsernameField()
    email = models.EmailField(unique=True, null=True)

    key_pair = fields.OneToOneField(
        'KeyPair',
        on_delete=models.CASCADE,
        blank=True, null=True,
        activitypub_field='publicKey',
        related_name='owner'
    )
    inbox = fields.RemoteIdField(unique=True)
    shared_inbox = fields.RemoteIdField(
        activitypub_field='sharedInbox',
        activitypub_wrapper='endpoints',
        deduplication_field=False,
        null=True)
    federated_server = models.ForeignKey(
        'FederatedServer',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    outbox = fields.RemoteIdField(unique=True)
    summary = fields.HtmlField(null=True, blank=True)
    local = models.BooleanField(default=False)
    bookwyrm_user = fields.BooleanField(default=True)
    localname = models.CharField(
        max_length=255,
        null=True,
        unique=True,
        validators=[fields.validate_localname],
    )
    # name is your display name, which you can change at will
    name = fields.CharField(max_length=100, null=True, blank=True)
    avatar = fields.ImageField(
        upload_to='avatars/', blank=True, null=True,
        activitypub_field='icon', alt_field='alt_text')
    followers = fields.ManyToManyField(
        'self',
        link_only=True,
        symmetrical=False,
        through='UserFollows',
        through_fields=('user_object', 'user_subject'),
        related_name='following'
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
    remote_id = fields.RemoteIdField(
        null=True, unique=True, activitypub_field='id')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    last_active_date = models.DateTimeField(auto_now=True)
    manually_approves_followers = fields.BooleanField(default=False)

    name_field = 'username'
    @property
    def alt_text(self):
        ''' alt text with username '''
        return 'avatar for %s' % (self.localname or self.username)

    @property
    def display_name(self):
        ''' show the cleanest version of the user's name possible '''
        if self.name and self.name != '':
            return self.name
        return self.localname or self.username

    activity_serializer = activitypub.Person

    def to_outbox(self, filter_type=None, **kwargs):
        ''' an ordered collection of statuses '''
        if filter_type:
            filter_class = apps.get_model(
                'bookwyrm.%s' % filter_type, require_ready=True)
            if not issubclass(filter_class, Status):
                raise TypeError(
                    'filter_status_class must be a subclass of models.Status')
            queryset = filter_class.objects
        else:
            queryset = Status.objects

        queryset = queryset.filter(
            user=self,
            deleted=False,
            privacy__in=['public', 'unlisted'],
        ).select_subclasses().order_by('-published_date')
        return self.to_ordered_collection(queryset, \
                remote_id=self.outbox, **kwargs)

    def to_following_activity(self, **kwargs):
        ''' activitypub following list '''
        remote_id = '%s/following' % self.remote_id
        return self.to_ordered_collection(
            self.following.order_by('-updated_date').all(),
            remote_id=remote_id,
            id_only=True,
            **kwargs
        )

    def to_followers_activity(self, **kwargs):
        ''' activitypub followers list '''
        remote_id = '%s/followers' % self.remote_id
        return self.to_ordered_collection(
            self.followers.order_by('-updated_date').all(),
            remote_id=remote_id,
            id_only=True,
            **kwargs
        )

    def to_activity(self):
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
        if not self.local and not re.match(regex.full_username, self.username):
            # generate a username that uses the domain (webfinger format)
            actor_parts = urlparse(self.remote_id)
            self.username = '%s@%s' % (self.username, actor_parts.netloc)
            return super().save(*args, **kwargs)

        if self.id or not self.local:
            return super().save(*args, **kwargs)

        # populate fields for local users
        self.remote_id = 'https://%s/user/%s' % (DOMAIN, self.localname)
        self.inbox = '%s/inbox' % self.remote_id
        self.shared_inbox = 'https://%s/inbox' % DOMAIN
        self.outbox = '%s/outbox' % self.remote_id

        return super().save(*args, **kwargs)

    @property
    def local_path(self):
        ''' this model doesn't inherit bookwyrm model, so here we are '''
        return '/user/%s' % (self.localname or self.username)


class KeyPair(ActivitypubMixin, BookWyrmModel):
    ''' public and private keys for a user '''
    private_key = models.TextField(blank=True, null=True)
    public_key = fields.TextField(
        blank=True, null=True, activitypub_field='publicKeyPem')

    activity_serializer = activitypub.PublicKey
    serialize_reverse_fields = [('owner', 'owner', 'id')]

    def get_remote_id(self):
        # self.owner is set by the OneToOneField on User
        return '%s/#main-key' % self.owner.remote_id

    def save(self, *args, **kwargs):
        ''' create a key pair '''
        if not self.public_key:
            self.private_key, self.public_key = create_key_pair()
        return super().save(*args, **kwargs)

    def to_activity(self):
        ''' override default AP serializer to add context object
            idk if this is the best way to go about this '''
        activity_object = super().to_activity()
        del activity_object['@context']
        del activity_object['type']
        return activity_object


class AnnualGoal(BookWyrmModel):
    ''' set a goal for how many books you read in a year '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    goal = models.IntegerField()
    year = models.IntegerField(default=timezone.now().year)
    privacy = models.CharField(
        max_length=255,
        default='public',
        choices=fields.PrivacyLevels.choices
    )

    class Meta:
        ''' unqiueness constraint '''
        unique_together = ('user', 'year')

    def get_remote_id(self):
        ''' put the year in the path '''
        return '%s/goal/%d' % (self.user.remote_id, self.year)

    @property
    def books(self):
        ''' the books you've read this year '''
        return self.user.readthrough_set.filter(
            finish_date__year__gte=self.year
        ).order_by('-finish_date').all()


    @property
    def ratings(self):
        ''' ratings for books read this year '''
        book_ids = [r.book.id for r in self.books]
        reviews = Review.objects.filter(
            user=self.user,
            book__in=book_ids,
        )
        return {r.book.id: r.rating for r in reviews}


    @property
    def progress_percent(self):
        ''' progress in an annual goal in percent form '''
        return int(float(self.book_count / self.goal) * 100)


    @property
    def book_count(self):
        ''' how many books you've read this year '''
        return self.user.readthrough_set.filter(
            finish_date__year__gte=self.year).count()



@receiver(models.signals.post_save, sender=User)
#pylint: disable=unused-argument
def execute_after_save(sender, instance, created, *args, **kwargs):
    ''' create shelves for new users '''
    if not created:
        return

    if not instance.local:
        set_remote_server.delay(instance.id)
        return

    instance.key_pair = KeyPair.objects.create(
        remote_id='%s/#main-key' % instance.remote_id)
    instance.save()

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


@app.task
def set_remote_server(user_id):
    ''' figure out the user's remote server in the background '''
    user = User.objects.get(id=user_id)
    actor_parts = urlparse(user.remote_id)
    user.federated_server = \
        get_or_create_remote_server(actor_parts.netloc)
    user.save()
    if user.bookwyrm_user:
        get_remote_reviews.delay(user.outbox)


def get_or_create_remote_server(domain):
    ''' get info on a remote server '''
    try:
        return FederatedServer.objects.get(
            server_name=domain
        )
    except FederatedServer.DoesNotExist:
        pass

    data = get_data('https://%s/.well-known/nodeinfo' % domain)

    try:
        nodeinfo_url = data.get('links')[0].get('href')
    except (TypeError, KeyError):
        return None

    data = get_data(nodeinfo_url)

    server = FederatedServer.objects.create(
        server_name=domain,
        application_type=data['software']['name'],
        application_version=data['software']['version'],
    )
    return server


@app.task
def get_remote_reviews(outbox):
    ''' ingest reviews by a new remote bookwyrm user '''
    outbox_page = outbox + '?page=true&type=Review'
    data = get_data(outbox_page)

    # TODO: pagination?
    for activity in data['orderedItems']:
        if not activity['type'] == 'Review':
            continue
        activitypub.Review(**activity).to_model(Review)
