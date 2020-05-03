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


def search(query, first=False):
    ''' find books based on arbitary keywords '''
    results = []
    for connector in get_connectors():
        result = connector.search(query)
        if first and result:
            return result[0]
        results.append({
            'connector': connector,
            'results': result,
        })

    return results


def update_book(book):
    ''' re-sync with the original data source '''
    connector = get_connector(book)
    connector.update_book(book)


def get_connectors():
    ''' load all connectors '''
    connectors_info = models.Connector.objects.order_by('priority').all()
    return [load_connector(c) for c in connectors_info]


def get_connector(book=None):
    ''' pick a book data connector '''
    if book and book.connector:
        connector_info = book.connector
    else:
        # only select from external connectors
        connector_info = models.Connector.objects.filter(
            local=False
        ).order_by('priority').first()
    return load_connector(connector_info)


def load_connector(connector_info):
    ''' instantiate the connector class '''
    connector = importlib.import_module(
        'fedireads.connectors.%s' % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)
