''' database schema for books and shelves '''
import re

from django.db import models
from django.db.models import Q
from django.utils import timezone
from model_utils.managers import InheritanceManager

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN
from bookwyrm.utils.fields import ArrayField

from .base_model import ActivityMapping, BookWyrmModel
from .base_model import ActivitypubMixin, OrderedCollectionPageMixin
from .base_model import image_attachments_formatter

class Book(ActivitypubMixin, BookWyrmModel):
    ''' a generic book, which can mean either an edition or a work '''
    origin_id = models.CharField(max_length=255, null=True, blank=True)
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

    @property
    def ap_parent_work(self):
        ''' reference the work via local id not remote '''
        return self.parent_work.remote_id

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),

        ActivityMapping('authors', 'ap_authors'),
        ActivityMapping('first_published_date', 'first_published_date'),
        ActivityMapping('published_date', 'published_date'),

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

        ActivityMapping('work', 'ap_parent_work'),
        ActivityMapping('isbn_10', 'isbn_10'),
        ActivityMapping('isbn_13', 'isbn_13'),
        ActivityMapping('oclc_number', 'oclc_number'),
        ActivityMapping('asin', 'asin'),
        ActivityMapping('pages', 'pages'),
        ActivityMapping('physical_format', 'physical_format'),
        ActivityMapping('publishers', 'publishers'),

        ActivityMapping('lccn', 'lccn'),
        ActivityMapping('editions', 'editions_path'),
        ActivityMapping(
            'attachment', 'cover',
            # this expects an iterable and the field is just an image
            lambda x: image_attachments_formatter([x]),
            lambda x: activitypub.image_attachments_formatter(x)[0]
        ),
    ]

    def save(self, *args, **kwargs):
        ''' can't be abstract for query reasons, but you shouldn't USE it '''
        if not isinstance(self, Edition) and not isinstance(self, Work):
            raise ValueError('Books should be added as Editions or Works')
        if self.id and not self.remote_id:
            self.remote_id = self.get_remote_id()

        super().save(*args, **kwargs)

    def get_remote_id(self):
        ''' editions and works both use "book" instead of model_name '''
        return 'https://%s/book/%d' % (DOMAIN, self.id)

    def __repr__(self):
        return "<{} key={!r} title={!r}>".format(
            self.__class__,
            self.openlibrary_key,
            self.title,
        )


class Work(OrderedCollectionPageMixin, Book):
    ''' a work (an abstract concept of a book that manifests in an edition) '''
    # library of congress catalog control number
    lccn = models.CharField(max_length=255, blank=True, null=True)
    # this has to be nullable but should never be null
    default_edition = models.ForeignKey(
        'Edition',
        on_delete=models.PROTECT,
        null=True
    )

    @property
    def editions_path(self):
        ''' it'd be nice to serialize the edition instead but, recursion '''
        default = self.default_edition
        ed_list = [
            e.remote_id for e in self.edition_set.filter(~Q(id=default.id)).all()
        ]
        return [default.remote_id] + ed_list


    def to_edition_list(self, **kwargs):
        ''' activitypub serialization for this work's editions '''
        remote_id = self.remote_id + '/editions'
        return self.to_ordered_collection(
            self.edition_set,
            remote_id=remote_id,
            **kwargs
        )


    activity_serializer = activitypub.Work


class Edition(Book):
    ''' an edition of a book '''
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

    def save(self, *args, **kwargs):
        ''' calculate isbn 10/13 '''
        if self.isbn_13 and self.isbn_13[:3] == '978' and not self.isbn_10:
            self.isbn_10 = isbn_13_to_10(self.isbn_13)
        if self.isbn_10 and not self.isbn_13:
            self.isbn_13 = isbn_10_to_13(self.isbn_10)

        super().save(*args, **kwargs)


def isbn_10_to_13(isbn_10):
    ''' convert an isbn 10 into an isbn 13 '''
    isbn_10 = re.sub(r'[^0-9X]', '', isbn_10)
    # drop the last character of the isbn 10 number (the original checkdigit)
    converted = isbn_10[:9]
    # add "978" to the front
    converted = '978' + converted
    # add a check digit to the end
    # multiply the odd digits by 1 and the even digits by 3 and sum them
    try:
        checksum = sum(int(i) for i in converted[::2]) + \
               sum(int(i) * 3 for i in converted[1::2])
    except ValueError:
        return None
    # add the checksum mod 10 to the end
    checkdigit = checksum % 10
    if checkdigit != 0:
        checkdigit = 10 - checkdigit
    return converted + str(checkdigit)


def isbn_13_to_10(isbn_13):
    ''' convert isbn 13 to 10, if possible '''
    if isbn_13[:3] != '978':
        return None

    isbn_13 = re.sub(r'[^0-9X]', '', isbn_13)

    # remove '978' and old checkdigit
    converted = isbn_13[3:-1]
    # calculate checkdigit
    # multiple each digit by 10,9,8.. successively and sum them
    try:
        checksum = sum(int(d) * (10 - idx) for (idx, d) in enumerate(converted))
    except ValueError:
        return None
    checkdigit = checksum % 11
    checkdigit = 11 - checkdigit
    if checkdigit == 10:
        checkdigit = 'X'
    return converted + str(checkdigit)


class Author(ActivitypubMixin, BookWyrmModel):
    origin_id = models.CharField(max_length=255, null=True)
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
        ActivityMapping('name', 'display_name'),
        ActivityMapping('born', 'born'),
        ActivityMapping('died', 'died'),
        ActivityMapping('aliases', 'aliases'),
        ActivityMapping('bio', 'bio'),
        ActivityMapping('openlibrary_key', 'openlibrary_key'),
        ActivityMapping('wikipedia_link', 'wikipedia_link'),
    ]
    activity_serializer = activitypub.Author
