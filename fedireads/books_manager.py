''' select and call a connector for whatever book task needs doing '''
import importlib

from fedireads import models
from fedireads.tasks import app


def get_or_create_book(key):
    ''' pull up a book record by whatever means possible '''
    try:
        book = models.Book.objects.select_subclasses().get(
            fedireads_key=key
        )
        return book
    except models.Book.DoesNotExist:
        pass

    connector = get_connector()
    book = connector.get_or_create_book(key)
    load_more_data.delay(book.id)
    return book


@app.task
def load_more_data(book_id):
    ''' background the work of getting all 10,000 editions of LoTR '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    connector = get_connector(book)
    connector.expand_book_data(book)


def search(query):
    ''' try an external datasource for books '''
    connector = get_connector()
    return connector.search(query)

def update_book(book):
    ''' re-sync with the original data source '''
    connector = get_connector(book)
    connector.update_book(book)


def get_connector(book=None):
    ''' pick a book data connector '''
    if book and book.connector:
        connector_info = book.connector
    else:
        connector_info = models.Connector.objects.first()

    connector = importlib.import_module(
        'fedireads.connectors.%s' % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)
