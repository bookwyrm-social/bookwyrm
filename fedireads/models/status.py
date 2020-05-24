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
    content = models.TextField(blank=True, null=True)
    mention_users = models.ManyToManyField('User', related_name='mention_user')
    mention_books = models.ManyToManyField(
        'Edition', related_name='mention_book')
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

    # ---- activitypub serialization settings for this model ----- #
    @property
    def ap_to(self):
        ''' should be related to post privacy I think '''
        return ['https://www.w3.org/ns/activitystreams#Public']

    @property
    def ap_cc(self):
        ''' should be related to post privacy I think '''
        return [self.user.ap_followers]

    @property
    def ap_replies(self):
        ''' structured replies block '''
        # TODO: actual replies
        return {}

    shared_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('url', 'remote_id'),
        ActivityMapping('inReplyTo', 'reply_parent'),
        ActivityMapping(
            'published',
            'published_date',
            lambda d: http_date(d.timestamp())
        ),
        ActivityMapping('attributedTo', 'user'),
        ActivityMapping('to', 'ap_to'),
        ActivityMapping('cc', 'ap_cc'),
        ActivityMapping('replies', 'ap_replies'),
    ]

    # serializing to fedireads expanded activitypub
    activity_mappings = shared_mappings + [
        ActivityMapping('name', 'name'),
        ActivityMapping('type', 'activity_type'),
        ActivityMapping('inReplyToBook', 'book'),
        ActivityMapping('rating', 'rating'),
        ActivityMapping('quote', 'quote'),
        ActivityMapping('content', 'content'),
    ]

    # for serializing to standard activitypub without extended types
    pure_activity_mappings = shared_mappings + [
        ActivityMapping('type', 'pure_activity_type'),
        ActivityMapping('name', 'pure_ap_name'),
        ActivityMapping('content', 'ap_pure_content'),
    ]

    activity_type = 'Note'
    activity_serializer = activitypub.Note


class Comment(Status):
    ''' like a review but without a rating and transient '''
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return self.content + '<br><br>(comment on <a href="%s">"%s"</a>)' % \
                (self.book.local_id, self.book.title)

    activity_type = 'Comment'
    pure_activity_type = 'Note'
    activity_serializer = activitypub.Comment
    pure_activity_serializer = activitypub.Note


class Quotation(Status):
    ''' like a review but without a rating and transient '''
    quote = models.TextField()
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return '"%s"<br>-- <a href="%s">"%s"</a>)<br><br>%s' % (
            self.quote,
            self.book.local_id,
            self.book.title,
            self.content,
        )

    activity_type = 'Quotation'
    pure_activity_type = 'Note'
    activity_serializer = activitypub.Quotation


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

    @property
    def ap_pure_name(self):
        ''' clarify review names for mastodon serialization '''
        return 'Review of "%s" (%d stars): %s' % (
            self.book.title,
            self.rating,
            self.name
        )

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return self.content + '<br><br>(<a href="%s">"%s"</a>)' % \
                (self.book.local_id, self.book.title)

    activity_type = 'Review'
    pure_activity_type = 'Article'
    activity_serializer = activitypub.Review


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
        ''' create a url-safe lookup key for the tag '''
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
