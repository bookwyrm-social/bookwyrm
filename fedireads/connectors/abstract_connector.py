''' functionality outline for a book data connector '''
from abc import ABC, abstractmethod

from fedireads.connectors import CONNECTORS


class AbstractConnector(ABC):
    ''' generic book data connector '''

    def __init__(self, connector_name):
        # load connector settings
        settings = CONNECTORS.get(connector_name)
        if not settings:
            raise ValueError('No connector with name "%s"' % connector_name)

        try:
            self.url = settings['BASE_URL']
            self.covers_url = settings['COVERS_URL']
            self.db_field = settings['DB_KEY_FIELD']
            self.key_name = settings['KEY_NAME']
        except KeyError:
            raise KeyError('Invalid connector settings')
        # TODO: politeness settings


    @abstractmethod
    def search(self, query):
        ''' free text search '''
        # return list of search result objs
        pass


    @abstractmethod
    def get_or_create_book(self, book_id):
        ''' request and format a book given an identifier '''
        # return book model obj
        pass


    @abstractmethod
    def get_or_create_author(self, book_id):
        ''' request and format a book given an identifier '''
        # return book model obj
        pass


    @abstractmethod
    def update_book(self, book_obj):
        ''' sync a book with the canonical remote copy '''
        # return book model obj
        pass


class SearchResult(object):
    ''' standardized search result object '''
    def __init__(self, title, key, author, year):
        self.title = title
        self.key = key
        self.author = author
        self.year = year
