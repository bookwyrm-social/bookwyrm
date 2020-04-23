''' functionality outline for a book data connector '''
from abc import ABC, abstractmethod
from dateutil import parser
import pytz

from fedireads import models


class AbstractConnector(ABC):
    ''' generic book data connector '''

    def __init__(self, identifier):
        # load connector settings
        info = models.Connector.objects.get(identifier=identifier)
        self.connector = info

        self.url = info.base_url
        self.covers_url = info.covers_url
        self.search_url = info.search_url
        self.key_name = info.key_name
        self.max_query_count = info.max_query_count


    def is_available(self):
        ''' check if you're allowed to use this connector '''
        if self.connector.max_query_count is not None:
            if self.connector.query_count >= self.connector.max_query_count:
                return False
        return True


    @abstractmethod
    def search(self, query):
        ''' free text search '''
        # return list of search result objs


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
    def update_book(self, book_obj):
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
    try:
        return pytz.utc.localize(parser.parse(date_string))
    except ValueError:
        return None


class SearchResult:
    ''' standardized search result object '''
    def __init__(self, title, key, author, year, raw_data):
        self.title = title
        self.key = key
        self.author = author
        self.year = year
        self.raw_data = raw_data

    def __repr__(self):
        return "<SearchResult key={!r} title={!r} author={!r}>".format(
            self.key, self.title, self.author)
