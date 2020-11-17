''' models for storing different kinds of Activities '''
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from model_utils.managers import InheritanceManager

from bookwyrm import activitypub
from .base_model import ActivitypubMixin, OrderedCollectionPageMixin
from .base_model import ActivityMapping, BookWyrmModel, PrivacyLevels


class Status(OrderedCollectionPageMixin, BookWyrmModel):
    ''' any post, like a reply to a review, etc '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    content = models.TextField(blank=True, null=True)
    mention_users = models.ManyToManyField('User', related_name='mention_user')
    mention_books = models.ManyToManyField(
        'Edition', related_name='mention_book')
    local = models.BooleanField(default=True)
    privacy = models.CharField(
        max_length=255,
        default='public',
        choices=PrivacyLevels.choices
    )
    sensitive = models.BooleanField(default=False)
    # the created date can't be this, because of receiving federated posts
    published_date = models.DateTimeField(default=timezone.now)
    deleted = models.BooleanField(default=False)
    deleted_date = models.DateTimeField(blank=True, null=True)
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
        return self.to_replies()

    @property
    def ap_tag(self):
        ''' references to books and/or users '''

        tags = []
        for book in self.mention_books.all():
            tags.append(activitypub.Link(
                href=book.remote_id,
                name=book.title,
                type='Book'
            ))
        for user in self.mention_users.all():
            tags.append(activitypub.Mention(
                href=user.remote_id,
                name=user.username,
            ))
        return tags

    @property
    def ap_status_image(self):
        ''' attach a book cover, if relevent '''
        if hasattr(self, 'book'):
            return self.book.ap_cover
        if self.mention_books.first():
            return self.mention_books.first().ap_cover
        return None


    shared_mappings = [
        ActivityMapping('url', 'remote_id', lambda x: None),
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('inReplyTo', 'reply_parent'),
        ActivityMapping('published', 'published_date'),
        ActivityMapping('attributedTo', 'user'),
        ActivityMapping('to', 'ap_to'),
        ActivityMapping('cc', 'ap_cc'),
        ActivityMapping('replies', 'ap_replies'),
        ActivityMapping('tag', 'ap_tag'),
    ]

    # serializing to bookwyrm expanded activitypub
    activity_mappings = shared_mappings + [
        ActivityMapping('name', 'name'),
        ActivityMapping('inReplyToBook', 'book'),
        ActivityMapping('rating', 'rating'),
        ActivityMapping('quote', 'quote'),
        ActivityMapping('content', 'content'),
    ]

    # for serializing to standard activitypub without extended types
    pure_activity_mappings = shared_mappings + [
        ActivityMapping('name', 'ap_pure_name'),
        ActivityMapping('content', 'ap_pure_content'),
        ActivityMapping('attachment', 'ap_status_image'),
    ]

    activity_serializer = activitypub.Note

    #----- replies collection activitypub ----#
    @classmethod
    def replies(cls, status):
        ''' load all replies to a status. idk if there's a better way
            to write this so it's just a property '''
        return cls.objects.filter(reply_parent=status).select_subclasses()

    @property
    def status_type(self):
        ''' expose the type of status for the ui using activity type '''
        return self.activity_serializer.__name__

    def to_replies(self, **kwargs):
        ''' helper function for loading AP serialized replies to a status '''
        return self.to_ordered_collection(
            self.replies(self),
            remote_id='%s/replies' % self.remote_id,
            **kwargs
        )

    def to_activity(self, pure=False):
        ''' return tombstone if the status is deleted '''
        if self.deleted:
            return activitypub.Tombstone(
                id=self.remote_id,
                url=self.remote_id,
                deleted=self.deleted_date.isoformat(),
                published=self.deleted_date.isoformat()
            ).serialize()
        return ActivitypubMixin.to_activity(self, pure=pure)

    def save(self, *args, **kwargs):
        ''' update user active time '''
        self.user.last_active_date = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)


class GeneratedNote(Status):
    ''' these are app-generated messages about user activity '''
    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        message = self.content
        books = ', '.join(
            '<a href="%s">"%s"</a>' % (self.book.remote_id, self.book.title) \
            for book in self.mention_books.all()
        )
        return '%s %s' % (message, books)

    activity_serializer = activitypub.GeneratedNote
    pure_activity_serializer = activitypub.Note


class Comment(Status):
    ''' like a review but without a rating and transient '''
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return self.content + '<br><br>(comment on <a href="%s">"%s"</a>)' % \
                (self.book.remote_id, self.book.title)

    activity_serializer = activitypub.Comment
    pure_activity_serializer = activitypub.Note


class Quotation(Status):
    ''' like a review but without a rating and transient '''
    quote = models.TextField()
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return '"%s"<br>-- <a href="%s">"%s"</a><br><br>%s' % (
            self.quote,
            self.book.remote_id,
            self.book.title,
            self.content,
        )

    activity_serializer = activitypub.Quotation
    pure_activity_serializer = activitypub.Note

#class Progress(Status):
#    ''' an update of where a user is in a book, using page number or % '''
#    class ProgressMode(models.TextChoices):
#        PAGE = 'PG', 'page'
#        PERCENT = 'PCT', 'percent'
#
#    progress = models.IntegerField()
#    mode = models.TextChoices(max_length=3, choices=ProgessMode.choices, default=ProgressMode.PAGE)
#    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
#
#    @property
#    def ap_pure_content(self):
#        ''' indicate the book in question for mastodon (or w/e) users '''
#        if self.mode == ProgressMode.PAGE:
#            return 'on page %d of %d in <a href="%s">"%s"</a>' % (
#                self.progress,
#                self.book.pages,
#                self.book.remote_id,
#                self.book.title,
#            )
#        else:
#            return '%d%% of the way through <a href="%s">"%s"</a>' % (
#                self.progress,
#                self.book.remote_id,
#                self.book.title,
#            )
#
#    activity_serializer = activitypub.Progress
#    pure_activity_serializer = activitypub.Note

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
        if self.rating:
            return 'Review of "%s" (%d stars): %s' % (
                self.book.title,
                self.rating,
                self.name
            )
        return 'Review of "%s": %s' % (
            self.book.title,
            self.name
        )

    @property
    def ap_pure_content(self):
        ''' indicate the book in question for mastodon (or w/e) users '''
        return self.content + '<br><br>(<a href="%s">"%s"</a>)' % \
                (self.book.remote_id, self.book.title)

    activity_serializer = activitypub.Review
    pure_activity_serializer = activitypub.Article


class Favorite(ActivitypubMixin, BookWyrmModel):
    ''' fav'ing a post '''
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    status = models.ForeignKey('Status', on_delete=models.PROTECT)

    # ---- activitypub serialization settings for this model ----- #
    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('actor', 'user'),
        ActivityMapping('object', 'status'),
    ]

    activity_serializer = activitypub.Like

    def save(self, *args, **kwargs):
        ''' update user active time '''
        self.user.last_active_date = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)


    class Meta:
        ''' can't fav things twice '''
        unique_together = ('user', 'status')


class Boost(Status):
    ''' boost'ing a post '''
    boosted_status = models.ForeignKey(
        'Status',
        on_delete=models.PROTECT,
        related_name="boosters")

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('actor', 'user'),
        ActivityMapping('object', 'boosted_status'),
    ]

    activity_serializer = activitypub.Boost

    # This constraint can't work as it would cross tables.
    # class Meta:
    #     unique_together = ('user', 'boosted_status')


class ReadThrough(BookWyrmModel):
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

    def save(self, *args, **kwargs):
        ''' update user active time '''
        self.user.last_active_date = timezone.now()
        self.user.save()
        super().save(*args, **kwargs)


NotificationType = models.TextChoices(
    'NotificationType',
    'FAVORITE REPLY MENTION TAG FOLLOW FOLLOW_REQUEST BOOST IMPORT')

class Notification(BookWyrmModel):
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
        ''' checks if notifcation is in enum list for valid types '''
        constraints = [
            models.CheckConstraint(
                check=models.Q(notification_type__in=NotificationType.values),
                name="notification_type_valid",
            )
        ]
