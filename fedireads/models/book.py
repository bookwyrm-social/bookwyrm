''' database schema for books and shelves '''
from django.utils import timezone
from django.db import models
from model_utils.managers import InheritanceManager

from fedireads import activitypub
from fedireads.settings import DOMAIN
from fedireads.utils.fields import JSONField, ArrayField
from fedireads.utils.models import FedireadsModel

from fedireads.connectors.settings import CONNECTORS


ConnectorFiles = models.TextChoices('ConnectorFiles', CONNECTORS)
class Connector(FedireadsModel):
    ''' book data source connectors '''
    identifier = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(default=2)
    name = models.CharField(max_length=255, null=True)
    local = models.BooleanField(default=False)
    connector_file = models.CharField(
        max_length=255,
        choices=ConnectorFiles.choices
    )
    api_key = models.CharField(max_length=255, null=True)

    base_url = models.CharField(max_length=255)
    books_url = models.CharField(max_length=255)
    covers_url = models.CharField(max_length=255)
    search_url = models.CharField(max_length=255, null=True)

    key_name = models.CharField(max_length=255)

    politeness_delay = models.IntegerField(null=True) #seconds
    max_query_count = models.IntegerField(null=True)
    # how many queries executed in a unit of time, like a day
    query_count = models.IntegerField(default=0)
    # when to reset the query count back to 0 (ie, after 1 day)
    query_count_expiry = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(connector_file__in=ConnectorFiles),
                name='connector_file_valid'
            )
        ]


class Book(FedireadsModel):
    ''' a generic book, which can mean either an edition or a work '''
    remote_id = models.CharField(max_length=255, null=True)
    # these identifiers apply to both works and editions
    openlibrary_key = models.CharField(max_length=255, blank=True, null=True)
    librarything_key = models.CharField(max_length=255, blank=True, null=True)
    goodreads_key = models.CharField(max_length=255, blank=True, null=True)
    misc_identifiers = JSONField(null=True)

    # info about where the data comes from and where/if to sync
    sync = models.BooleanField(default=True)
    sync_cover = models.BooleanField(default=True)
    last_sync_date = models.DateTimeField(default=timezone.now)
    connector = models.ForeignKey(
        'Connector', on_delete=models.PROTECT, null=True)

    # TODO: edit history

    # book/work metadata
    title = models.CharField(max_length=255)
    sort_title = models.CharField(max_length=255, blank=True, null=True)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    languages = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    series = models.CharField(max_length=255, blank=True, null=True)
    series_number = models.CharField(max_length=255, blank=True, null=True)
    subjects = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    subject_places = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    # TODO: include an annotation about the type of authorship (ie, translator)
    authors = models.ManyToManyField('Author')
    # preformatted authorship string for search and easier display
    author_text = models.CharField(max_length=255, blank=True, null=True)
    cover = models.ImageField(upload_to='covers/', blank=True, null=True)
    first_published_date = models.DateTimeField(blank=True, null=True)
    published_date = models.DateTimeField(blank=True, null=True)
    objects = InheritanceManager()

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        if self.sync and self.remote_id:
            return self.remote_id
        base_path = 'https://%s' % DOMAIN
        return '%s/book/%d' % (base_path, self.id)

    def save(self, *args, **kwargs):
        ''' can't be abstract for query reasons, but you shouldn't USE it '''
        if not isinstance(self, Edition) and not isinstance(self, Work):
            raise ValueError('Books should be added as Editions or Works')
        super().save(*args, **kwargs)

    def __repr__(self):
        return "<{} key={!r} title={!r}>".format(
            self.__class__,
            self.openlibrary_key,
            self.title,
        )

    @property
    def activitypub_serialize(self):
        return activitypub.get_book(self)


class Work(Book):
    ''' a work (an abstract concept of a book that manifests in an edition) '''
    # library of congress catalog control number
    lccn = models.CharField(max_length=255, blank=True, null=True)

    @property
    def default_edition(self):
        ed = Edition.objects.filter(parent_work=self, default=True).first()
        if not ed:
            ed = Edition.objects.filter(parent_work=self).first()
        return ed


class Edition(Book):
    ''' an edition of a book '''
    # default -> this is what gets displayed for a work
    default = models.BooleanField(default=False)

    # these identifiers only apply to editions, not works
    isbn_10 = models.CharField(max_length=255, blank=True, null=True)
    isbn_13 = models.CharField(max_length=255, blank=True, null=True)
    oclc_number = models.CharField(max_length=255, blank=True, null=True)
    asin = models.CharField(max_length=255, blank=True, null=True)
    pages = models.IntegerField(blank=True, null=True)
    physical_format = models.CharField(max_length=255, blank=True, null=True)
    publishers = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    shelves = models.ManyToManyField(
        'Shelf',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('book', 'shelf')
    )
    parent_work = models.ForeignKey('Work', on_delete=models.PROTECT, null=True)


class Author(FedireadsModel):
    ''' copy of an author from OL '''
    remote_id = models.CharField(max_length=255, null=True)
    openlibrary_key = models.CharField(max_length=255, blank=True, null=True)
    sync = models.BooleanField(default=True)
    last_sync_date = models.DateTimeField(default=timezone.now)
    wikipedia_link = models.CharField(max_length=255, blank=True, null=True)
    # idk probably other keys would be useful here?
    born = models.DateTimeField(blank=True, null=True)
    died = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    aliases = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = models.TextField(null=True, blank=True)

    @property
    def activitypub_serialize(self):
        return activitypub.get_author(self)
