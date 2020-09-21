''' database schema for books and shelves '''
from django.db import models
from django.utils import timezone
from django.utils.http import http_date
from model_utils.managers import InheritanceManager

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from bookwyrm.utils.fields import ArrayField

from .base_model import ActivityMapping, ActivitypubMixin, FedireadsModel


class Book(ActivitypubMixin, FedireadsModel):
    ''' a generic book, which can mean either an edition or a work '''
    # these identifiers apply to both works and editions
    openlibrary_key = models.CharField(max_length=255, blank=True, null=True)
    librarything_key = models.CharField(max_length=255, blank=True, null=True)
    goodreads_key = models.CharField(max_length=255, blank=True, null=True)

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
    def ap_authors(self):
        ''' the activitypub serialization should be a list of author ids '''
        return [a.remote_id for a in self.authors.all()]

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),

        ActivityMapping('authors', 'ap_authors'),
        ActivityMapping(
            'first_published_date',
            'first_published_date',
            activity_formatter=lambda d: http_date(d.timestamp()) if d else None
        ),
        ActivityMapping(
            'published_date',
            'published_date',
            activity_formatter=lambda d: http_date(d.timestamp()) if d else None
        ),

        ActivityMapping('title', 'title'),
        ActivityMapping('sort_title', 'sort_title'),
        ActivityMapping('subtitle', 'subtitle'),
        ActivityMapping('description', 'description'),
        ActivityMapping('languages', 'languages'),
        ActivityMapping('series', 'series'),
        ActivityMapping('series_number', 'series_number'),
        ActivityMapping('subjects', 'subjects'),
        ActivityMapping('subject_places', 'subject_places'),

        ActivityMapping('openlibrary_key', 'openlibrary_key'),
        ActivityMapping('librarything_key', 'librarything_key'),
        ActivityMapping('goodreads_key', 'goodreads_key'),

        ActivityMapping('work', 'parent_work'),
        ActivityMapping('isbn_10', 'isbn_10'),
        ActivityMapping('isbn_13', 'isbn_13'),
        ActivityMapping('oclc_number', 'oclc_number'),
        ActivityMapping('asin', 'asin'),
        ActivityMapping('pages', 'pages'),
        ActivityMapping('physical_format', 'physical_format'),
        ActivityMapping('publishers', 'publishers'),

        ActivityMapping('lccn', 'lccn'),
        ActivityMapping('editions', 'editions_path'),
    ]

    def save(self, *args, **kwargs):
        ''' can't be abstract for query reasons, but you shouldn't USE it '''
        if not isinstance(self, Edition) and not isinstance(self, Work):
            raise ValueError('Books should be added as Editions or Works')

        super().save(*args, **kwargs)

    def get_remote_id(self):
        ''' editions and works both use "book" instead of model_name '''
        return 'https://%s/book/%d' % (DOMAIN, self.id)


    @property
    def local_id(self):
        ''' when a book is ingested from an outside source, it becomes local to
        an instance, so it needs a local url for federation. but it still needs
        the remote_id for easier deduplication and, if appropriate, to sync with
        the remote canonical copy '''
        return 'https://%s/book/%d' % (DOMAIN, self.id)

    def __repr__(self):
        return "<{} key={!r} title={!r}>".format(
            self.__class__,
            self.openlibrary_key,
            self.title,
        )


class Work(Book):
    ''' a work (an abstract concept of a book that manifests in an edition) '''
    # library of congress catalog control number
    lccn = models.CharField(max_length=255, blank=True, null=True)

    @property
    def editions_path(self):
        ''' it'd be nice to serialize the edition instead but, recursion '''
        return self.remote_id + '/editions'


    @property
    def default_edition(self):
        ''' best-guess attempt at picking the default edition for this work '''
        ed = Edition.objects.filter(parent_work=self, default=True).first()
        if not ed:
            ed = Edition.objects.filter(parent_work=self).first()
        return ed

    activity_serializer = activitypub.Work


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

    activity_serializer = activitypub.Edition


class Author(ActivitypubMixin, FedireadsModel):
    ''' copy of an author from OL '''
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
    def local_id(self):
        ''' when a book is ingested from an outside source, it becomes local to
        an instance, so it needs a local url for federation. but it still needs
        the remote_id for easier deduplication and, if appropriate, to sync with
        the remote canonical copy (ditto here for author)'''
        return 'https://%s/book/%d' % (DOMAIN, self.id)

    @property
    def display_name(self):
        ''' Helper to return a displayable name'''
        if self.name:
            return self.name
        # don't want to return a spurious space if all of these are None
        if self.first_name and self.last_name:
            return self.first_name + ' ' + self.last_name
        return self.last_name or self.first_name

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('url', 'remote_id'),
        ActivityMapping('name', 'display_name'),
        ActivityMapping('born', 'born'),
        ActivityMapping('died', 'died'),
        ActivityMapping('aliases', 'aliases'),
        ActivityMapping('bio', 'bio'),
        ActivityMapping('openlibrary_key', 'openlibrary_key'),
        ActivityMapping('wikipedia_link', 'wikipedia_link'),
    ]
    activity_serializer = activitypub.Author
