''' database schema for books and shelves '''
from datetime import datetime
from django.db import models
from model_utils.managers import InheritanceManager
from uuid import uuid4

from fedireads.settings import DOMAIN
from fedireads.utils.fields import JSONField, ArrayField
from fedireads.utils.models import FedireadsModel

from fedireads.connectors.settings import CONNECTORS


ConnectorFiles = models.TextChoices('ConnectorFiles', CONNECTORS)
class Connector(FedireadsModel):
    ''' book data source connectors '''
    identifier = models.CharField(max_length=255, unique=True)
    connector_file = models.CharField(
        max_length=255,
        default='openlibrary',
        choices=ConnectorFiles.choices
    )
    # is this a connector to your own database, should only be true if
    # the connector_file is `fedireads`
    is_self = models.BooleanField(default=False)
    api_key = models.CharField(max_length=255, null=True)

    base_url = models.CharField(max_length=255)
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
    # these identifiers apply to both works and editions
    openlibrary_key = models.CharField(max_length=255, unique=True, null=True)
    librarything_key = models.CharField(max_length=255, unique=True, null=True)
    fedireads_key = models.CharField(max_length=255, unique=True, default=uuid4)
    misc_identifiers = JSONField(null=True)

    # info about where the data comes from and where/if to sync
    source_url = models.CharField(max_length=255, unique=True, null=True)
    sync = models.BooleanField(default=True)
    last_sync_date = models.DateTimeField(default=datetime.now)
    connector = models.ForeignKey(
        'Connector', on_delete=models.PROTECT, null=True)

    # TODO: edit history

    # book/work metadata
    title = models.CharField(max_length=255)
    sort_title = models.CharField(max_length=255, null=True)
    subtitle = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=255, null=True)
    series = models.CharField(max_length=255, blank=True, null=True)
    series_number = models.CharField(max_length=255, blank=True, null=True)
    # TODO: include an annotation about the type of authorship (ie, translator)
    authors = models.ManyToManyField('Author')
    # TODO: also store cover thumbnail
    cover = models.ImageField(upload_to='covers/', blank=True, null=True)
    first_published_date = models.DateTimeField(null=True)
    published_date = models.DateTimeField(null=True)
    shelves = models.ManyToManyField(
        'Shelf',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('book', 'shelf')
    )
    parent_work = models.ForeignKey('Work', on_delete=models.PROTECT, null=True)
    objects = InheritanceManager()

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        base_path = 'https://%s' % DOMAIN
        model_name = type(self).__name__.lower()
        return '%s/%s/%s' % (base_path, model_name, self.openlibrary_key)

    def __repr__(self):
        return "<{} key={!r} title={!r} author={!r}>".format(
            self.__class__,
            self.openlibrary_key,
            self.title,
            self.author
        )


class Work(Book):
    ''' a work (an abstract concept of a book that manifests in an edition) '''
    # library of congress catalog control number
    lccn = models.CharField(max_length=255, unique=True, null=True)


class Edition(Book):
    ''' an edition of a book '''
    # these identifiers only apply to work
    isbn = models.CharField(max_length=255, unique=True, null=True)
    oclc_number = models.CharField(max_length=255, unique=True, null=True)
    pages = models.IntegerField(null=True)


class Author(FedireadsModel):
    ''' copy of an author from OL '''
    openlibrary_key = models.CharField(max_length=255, null=True, unique=True)
    wikipedia_link = models.CharField(max_length=255, blank=True, null=True)
    # idk probably other keys would be useful here?
    born = models.DateTimeField(null=True)
    died = models.DateTimeField(null=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    aliases = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    bio = models.TextField(null=True, blank=True)

