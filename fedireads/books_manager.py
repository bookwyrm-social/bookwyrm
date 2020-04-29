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
    self = self_connector()
    results = self.search(query)
    if len(results) >= 10:
        return results

    connector = get_connector()
    external_results = connector.search(query)
    dedupe_slug = lambda r: '%s %s %s' % (r.title, r.author, r.year)
    result_index = [dedupe_slug(r) for r in results]
    for result in external_results:
        if dedupe_slug(result) in result_index:
            continue
        results.append(result)

    return results

def update_book(book):
    ''' re-sync with the original data source '''
    connector = get_connector(book)
    connector.update_book(book)


def self_connector():
    ''' load the connector for the local database '''
    return get_connector(self=True)


def get_connector(book=None, self=False):
    ''' pick a book data connector '''
    if book and book.connector:
        connector_info = book.connector
    elif self:
        connector_info = models.Connector.objects.filter(
            connector_file='self_connector'
        ).first()
    else:
        # only select from external connectors
        connector_info = models.Connector.objects.exclude(
            connector_file='self_connector'
        ).first()

    connector = importlib.import_module(
        'fedireads.connectors.%s' % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)
