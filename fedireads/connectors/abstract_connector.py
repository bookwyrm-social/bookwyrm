''' functionality outline for a book data connector '''
from abc import ABC, abstractmethod
from dateutil import parser
import pytz
import requests

from fedireads import models


class AbstractConnector(ABC):
    ''' generic book data connector '''

    def __init__(self, identifier):
        # load connector settings
        info = models.Connector.objects.get(identifier=identifier)
        self.connector = info

        self.book_mappings = {}

        self.base_url = info.base_url
        self.books_url = info.books_url
        self.covers_url = info.covers_url
        self.search_url = info.search_url
        self.key_name = info.key_name
        self.max_query_count = info.max_query_count
        self.name = info.name
        self.local = info.local
        self.id = info.id


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


    def create_book(self, key, data, model):
        ''' create a work or edition from data '''
        # we really would rather use an existing book than make a new one
        match = match_from_mappings(data, self.key_mappings)
        if match:
            if not isinstance(match, model):
                if type(match).__name__ == 'Edition':
                    return match.parent_work
                else:
                    return match.default_edition
            return match

        kwargs = {
            self.key_name: key,
            'title': data['title'],
            'connector': self.connector
        }
        book = model.objects.create(**kwargs)
        return self.update_book_from_data(book, data)


    def update_book_from_data(self, book, data):
        ''' simple function to save data to a book '''
        update_from_mappings(book, data, self.book_mappings)
        book.save()
        return book


    @abstractmethod
    def parse_search_data(self, data):
        ''' turn the result json from a search into a list '''


    @abstractmethod
    def format_search_result(self, search_result):
        ''' create a SearchResult obj from json '''


    @abstractmethod
    def get_or_create_book(self, book_id):
        ''' request and format a book given an identifier '''
        # return book model obj


    @abstractmethod
    def expand_book_data(self, book):
        ''' get more info on a book '''


    @abstractmethod
    def get_or_create_author(self, book_id):
        ''' request and format a book given an identifier '''
        # return book model obj


    @abstractmethod
    def update_book(self, book_obj, data=None):
        ''' sync a book with the canonical remote copy '''
        # return book model obj


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


def match_from_mappings(data, mappings):
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
        if key in mappings:
            key, formatter = mappings[key]
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


def has_attr(obj, key):
    ''' helper function to check if a model object has a key '''
    try:
        return hasattr(obj, key)
    except ValueError:
        return False


def get_date(date_string):
    ''' helper function to try to interpret dates '''
    try:
        return pytz.utc.localize(parser.parse(date_string))
    except ValueError:
        return None


class SearchResult:
    ''' standardized search result object '''
    def __init__(self, title, key, author, year):
        self.title = title
        self.key = key
        self.author = author
        self.year = year

    def __repr__(self):
        return "<SearchResult key={!r} title={!r} author={!r}>".format(
            self.key, self.title, self.author)
