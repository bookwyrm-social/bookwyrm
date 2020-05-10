''' functionality outline for a book data connector '''
from abc import ABC, abstractmethod
from dateutil import parser
import pytz
import requests

from django.db import transaction

from fedireads import models


class AbstractConnector(ABC):
    ''' generic book data connector '''

    def __init__(self, identifier):
        # load connector settings
        info = models.Connector.objects.get(identifier=identifier)
        self.connector = info

        self.book_mappings = {}
        self.key_mappings = {
            'isbn_13': ('isbn_13', None),
            'isbn_10': ('isbn_10', None),
            'oclc_numbers': ('oclc_number', None),
            'lccn': ('lccn', None),
        }

        fields = [
            'base_url',
            'books_url',
            'covers_url',
            'search_url',
            'key_name',
            'max_query_count',
            'name',
            'identifier',
            'local'
        ]
        for field in fields:
            setattr(self, field, getattr(info, field))


    def is_available(self):
        ''' check if you're allowed to use this connector '''
        if self.max_query_count is not None:
            if self.connector.query_count >= self.max_query_count:
                return False
        return True


    def search(self, query):
        ''' free text search '''
        resp = requests.get(
            '%s%s' % (self.search_url, query),
            headers={
                'Accept': 'application/json; charset=utf-8',
            },
        )
        if not resp.ok:
            resp.raise_for_status()
        data = resp.json()
        results = []

        for doc in self.parse_search_data(data)[:10]:
            results.append(self.format_search_result(doc))
        return results


    def get_or_create_book(self, remote_id):
        ''' pull up a book record by whatever means possible '''
        # try to load the book
        book = models.Book.objects.select_subclasses().filter(
            remote_id=remote_id
        ).first()
        if book:
            if isinstance(book, models.Work):
                return book.default_edition
            return book

        # no book was found, so we start creating a new one
        data = get_data(remote_id)

        work = None
        edition = None
        if self.is_work_data(data):
            work_data = data
            # if we requested a work and there's already an edition, we're set
            work = self.match_from_mappings(work_data)
            if work and work.default_edition:
                return work.default_edition

            # no such luck, we need more information.
            try:
                edition_data = self.get_edition_from_work_data(work_data)
            except KeyError:
                # hack: re-use the work data as the edition data
                # this is why remote ids aren't necessarily unique
                edition_data = data
        else:
            edition_data = data
            edition = self.match_from_mappings(edition_data)
            # no need to figure out about the work if we already know about it
            if edition and edition.parent_work:
                return edition

            # no such luck, we need more information.
            try:
                work_data = self.get_work_from_edition_date(edition_data)
            except KeyError:
                # remember this hack: re-use the work data as the edition data
                work_data = data

        # at this point, we need to figure out the work, edition, or both
        # atomic so that we don't save a work with no edition for vice versa
        with transaction.atomic():
            if not work:
                work_key = work_data.get('url')
                work = self.create_book(work_key, work_data, models.Work)

            if not edition:
                ed_key = edition_data.get('url')
                edition = self.create_book(ed_key, edition_data, models.Edition)
                edition.default = True
                edition.parent_work = work
                edition.save()

        # now's our change to fill in author gaps
        if not edition.authors and work.authors:
            edition.authors.set(work.authors.all())
            edition.author_text = work.author_text
            edition.save()

        return edition


    def create_book(self, remote_id, data, model):
        ''' create a work or edition from data '''
        book = model.objects.create(
            remote_id=remote_id,
            title=data['title'],
            connector=self.connector,
        )
        return self.update_book_from_data(book, data)


    def update_book_from_data(self, book, data, update_cover=True):
        ''' for creating a new book or syncing with data '''
        book = update_from_mappings(book, data, self.book_mappings)

        for author in self.get_authors_from_data(data):
            book.authors.add(author)
        book.author_text = ', '.join(a.name for a in book.authors.all())
        book.save()

        if not update_cover:
            return book

        cover = self.get_cover_from_data(data)
        if cover:
            book.cover.save(*cover, save=True)
        return book


    def update_book(self, book, data=None):
        ''' load new data '''
        if not book.sync and not book.sync_cover:
            return

        if not data:
            key = getattr(book, self.key_name)
            data = self.load_book_data(key)

        if book.sync:
            book = self.update_book_from_data(
                book, data, update_cover=book.sync_cover)
        else:
            cover = self.get_cover_from_data(data)
            if cover:
                book.cover.save(*cover, save=True)

        return book


    def match_from_mappings(self, data):
        ''' try to find existing copies of this book using various keys '''
        keys = [
            ('openlibrary_key', models.Book),
            ('librarything_key', models.Book),
            ('goodreads_key', models.Book),
            ('lccn', models.Work),
            ('isbn_10', models.Edition),
            ('isbn_13', models.Edition),
            ('oclc_number', models.Edition),
            ('asin', models.Edition),
        ]
        noop = lambda x: x
        for key, model in keys:
            formatter = None
            if key in self.key_mappings:
                key, formatter = self.key_mappings[key]
            if not formatter:
                formatter = noop

            value = data.get(key)
            if not value:
                continue
            value = formatter(value)

            match = model.objects.select_subclasses().filter(
                **{key: value}).first()
            if match:
                return match


    @abstractmethod
    def is_work_data(self, data):
        ''' differentiate works and editions '''


    @abstractmethod
    def get_edition_from_work_data(self, data):
        ''' every work needs at least one edition '''


    @abstractmethod
    def get_work_from_edition_date(self, data):
        ''' every edition needs a work '''


    @abstractmethod
    def get_authors_from_data(self, data):
        ''' load author data '''


    @abstractmethod
    def get_cover_from_data(self, data):
        ''' load cover '''


    @abstractmethod
    def parse_search_data(self, data):
        ''' turn the result json from a search into a list '''


    @abstractmethod
    def format_search_result(self, search_result):
        ''' create a SearchResult obj from json '''


    @abstractmethod
    def expand_book_data(self, book):
        ''' get more info on a book '''


def update_from_mappings(obj, data, mappings):
    ''' assign data to model with mappings '''
    noop = lambda x: x
    mappings['authors'] = ('', noop)
    mappings['parent_work'] = ('', noop)
    for (key, value) in data.items():
        formatter = None
        if key in mappings:
            key, formatter = mappings[key]
        if not formatter:
            formatter = noop

        if key == 'id':
            continue

        if has_attr(obj, key):
            obj.__setattr__(key, formatter(value))
    return obj


def has_attr(obj, key):
    ''' helper function to check if a model object has a key '''
    try:
        return hasattr(obj, key)
    except ValueError:
        return False


def get_date(date_string):
    ''' helper function to try to interpret dates '''
    if not date_string:
        return None

    try:
        return pytz.utc.localize(parser.parse(date_string))
    except ValueError:
        pass

    try:
        return parser.parse(date_string)
    except ValueError:
        return None


def get_data(url):
    ''' wrapper for request.get '''
    resp = requests.get(
        url,
        headers={
            'Accept': 'application/json; charset=utf-8',
        },
    )
    if not resp.ok:
        resp.raise_for_status()
    data = resp.json()
    return data


class SearchResult(object):
    ''' standardized search result object '''
    def __init__(self, title, key, author, year):
        self.title = title
        self.key = key
        self.author = author
        self.year = year

    def __repr__(self):
        return "<SearchResult key={!r} title={!r} author={!r}>".format(
            self.key, self.title, self.author)
