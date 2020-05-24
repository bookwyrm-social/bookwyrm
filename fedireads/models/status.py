''' models for storing different kinds of Activities '''
import urllib.parse

from django.utils import timezone
from django.utils.http import http_date
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from model_utils.managers import InheritanceManager

from fedireads import activitypub
from .base_model import ActivityMapping, ActivitypubMixin, FedireadsModel


class Status(ActivitypubMixin, FedireadsModel):
    ''' any post, like a reply to a review, etc '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    status_type = models.CharField(max_length=255, default='Note')
    content = models.TextField(blank=True, null=True)
    mention_users = models.ManyToManyField('User', related_name='mention_user')
    mention_books = models.ManyToManyField(
        'Edition', related_name='mention_book')
    activity_type = models.CharField(max_length=255, default='Note')
    local = models.BooleanField(default=True)
    privacy = models.CharField(max_length=255, default='public')
    sensitive = models.BooleanField(default=False)
    # the created date can't be this, because of receiving federated posts
    published_date = models.DateTimeField(default=timezone.now)
    favorites = models.ManyToManyField(
        'User',
        symmetrical=False,
        through='Favorite',
        through_fields=('status', 'user'),
        related_name='user_favorites'
    )
    reply_parent = models.ForeignKey(
        'self',
        null=True,
        on_delete=models.PROTECT
    )
    objects = InheritanceManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    # ---- activitypub serialization settings for this model ----- #
    @property
    def ap_reply_parent(self):
        return self.reply_parent.remote_id

    @property
    def ap_date(self):
        return http_date(self.published_date.timestamp())

    @property
    def ap_user(self):
        return self.user.remote_id

    @property
    def ap_to(self):
        return ['https://www.w3.org/ns/activitystreams#Public']

    @property
    def ap_cc(self):
        return ['https://friend.camp/users/tripofmice/followers']

    @property
    def ap_replies(self):
        # TODO
        return {}


    model_to_activity = [
        ('id', 'remote_id'),
        ('type', 'activity_type'),
        ('url', 'remote_id'),
        ('inReplyTo', 'ap_reply_parent'),
        ('published', 'ap_date'),
        ('attributedTo', 'ap_user'),
        ('to', 'ap_to'),
        ('cc', 'ap_cc'),
        ('content', 'content'),
        ('replies', 'ap_replies'),
    ]
    activity_serializer = activitypub.Note

    activity_to_model = [
        ActivityMapping('remote_id', 'id'),
        ActivityMapping('activity_type', 'type'),
        ActivityMapping('reply_parent', 'inReplyTo'),
        ActivityMapping('published_date', 'published'),
        ActivityMapping('user', 'attributedTo'),
        ActivityMapping('content', 'content'),
    ]



class Comment(Status):
    ''' like a review but without a rating and transient '''
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        self.status_type = 'Comment'
        self.activity_type = 'Note'
        super().save(*args, **kwargs)


    @property
    def activitypub_serialize(self):
        return activitypub.get_comment(self)


class Quotation(Status):
    ''' like a review but without a rating and transient '''
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    quote = models.TextField()

    def save(self, *args, **kwargs):
        self.status_type = 'Quotation'
        self.activity_type = 'Note'
        super().save(*args, **kwargs)


    @property
    def activitypub_serialize(self):
        return activitypub.get_quotation(self)


class Review(Status):
    ''' a book review '''
    name = models.CharField(max_length=255, null=True)
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    rating = models.IntegerField(
        default=None,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    def save(self, *args, **kwargs):
        self.status_type = 'Review'
        self.activity_type = 'Article'
        super().save(*args, **kwargs)


    @property
    def activitypub_serialize(self):
        return activitypub.get_review(self)


class Favorite(FedireadsModel):
    ''' fav'ing a post '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    status = models.ForeignKey('Status', on_delete=models.PROTECT)

    class Meta:
        unique_together = ('user', 'status')


class Boost(Status):
    ''' boost'ing a post '''
    boosted_status = models.ForeignKey(
        'Status',
        on_delete=models.PROTECT,
        related_name="boosters")

    def save(self, *args, **kwargs):
        self.status_type = 'Boost'
        self.activity_type = 'Announce'
        super().save(*args, **kwargs)

    # This constraint can't work as it would cross tables.
    # class Meta:
    #     unique_together = ('user', 'boosted_status')

class Tag(FedireadsModel):
    ''' freeform tags for books '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)

    def save(self, *args, **kwargs):
        if not self.id:
            # add identifiers to new tags
            self.identifier = urllib.parse.quote_plus(self.name)
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('user', 'book', 'name')


class ReadThrough(FedireadsModel):
    ''' Store progress through a book in the database. '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    pages_read = models.IntegerField(
        null=True,
        blank=True)
    start_date = models.DateTimeField(
        blank=True,
        null=True)
    finish_date = models.DateTimeField(
        blank=True,
        null=True)


NotificationType = models.TextChoices(
    'NotificationType',
    'FAVORITE REPLY TAG FOLLOW FOLLOW_REQUEST BOOST IMPORT')

class Notification(FedireadsModel):
    ''' you've been tagged, liked, followed, etc '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    related_book = models.ForeignKey(
        'Edition', on_delete=models.PROTECT, null=True)
    related_user = models.ForeignKey(
        'User',
        on_delete=models.PROTECT, null=True, related_name='related_user')
    related_status = models.ForeignKey(
        'Status', on_delete=models.PROTECT, null=True)
    related_import = models.ForeignKey(
        'ImportJob', on_delete=models.PROTECT, null=True)
    read = models.BooleanField(default=False)
    notification_type = models.CharField(
        max_length=255, choices=NotificationType.choices)
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(notification_type__in=NotificationType.values),
                name="notification_type_valid",
            )
        ]
