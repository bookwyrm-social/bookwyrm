''' select and call a connector for whatever book task needs doing '''
import importlib

from fedireads import models
from fedireads.connectors.settings import CONNECTORS


def get_or_create_book(key):
    ''' pull up a book record by whatever means possible '''
    try:
        book = models.Book.objects.get(
            openlibrary_key=key
        ).select_subclasses()
        return book
    except models.Book.DoesNotExist:
        pass

    connector = get_connector()
    return connector.get_or_create_book(key)


def search(query):
    ''' ya '''
    connector = get_connector()
    return connector.search(query)


def get_connector(book=None):
    ''' pick a book data connector '''
    if book and book.connector:
        connector_info = book.connector
    else:
        connector_info = models.Connector.objects.first()

    classname = CONNECTORS[connector_info.name]['classname']
    connector = importlib.import_module(classname)
    return connector.Connector()
