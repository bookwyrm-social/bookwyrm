''' select and call a connector for whatever book task needs doing '''
import importlib
from urllib.parse import urlparse

from requests import HTTPError

from fedireads import models
from fedireads.tasks import app


def get_edition(book_id):
    ''' look up a book in the db and return an edition '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    if isinstance(book, models.Work):
        book = book.default_edition
    return book


def get_or_create_book(remote_id):
    ''' pull up a book record by whatever means possible '''
    book = models.Book.objects.select_subclasses().filter(
        remote_id=remote_id
    ).first()
    if book:
        return book

    connector = get_or_create_connector(remote_id)

    book = connector.get_or_create_book(remote_id)
    load_more_data.delay(book.id)
    return book


def get_or_create_connector(remote_id):
    ''' get the connector related to the author's server '''
    url = urlparse(remote_id)
    identifier = url.netloc
    if not identifier:
        raise ValueError('Invalid remote id')

    try:
        connector_info = models.Connector.objects.get(identifier=identifier)
    except models.Connector.DoesNotExist:
        connector_info = models.Connector.objects.create(
            identifier=identifier,
            connector_file='fedireads_connector',
            base_url='https://%s' % identifier,
            books_url='https://%s/book' % identifier,
            covers_url='https://%s/images/covers' % identifier,
            search_url='https://%s/search?q=' % identifier,
            priority=3
        )

    return load_connector(connector_info)


@app.task
def load_more_data(book_id):
    ''' background the work of getting all 10,000 editions of LoTR '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    connector = load_connector(book.connector)
    connector.expand_book_data(book)


def search(query):
    ''' find books based on arbitary keywords '''
    results = []
    dedup_slug = lambda r: '%s/%s/%s' % (r.title, r.author, r.year)
    result_index = set()
    for connector in get_connectors():
        try:
            result_set = connector.search(query)
        except HTTPError:
            continue

        result_set = [r for r in result_set \
                if dedup_slug(r) not in result_index]
        # `|=` concats two sets. WE ARE GETTING FANCY HERE
        result_index |= set(dedup_slug(r) for r in result_set)
        results.append({
            'connector': connector,
            'results': result_set,
        })

    return results


def local_search(query):
    ''' only look at local search results '''
    connector = load_connector(models.Connector.objects.get(local=True))
    return connector.search(query)


def first_search_result(query):
    ''' search until you find a result that fits '''
    for connector in get_connectors():
        result = connector.search(query)
        if result:
            return result[0]
    return None


def update_book(book, data=None):
    ''' re-sync with the original data source '''
    connector = load_connector(book.connector)
    connector.update_book(book, data=data)


def get_connectors():
    ''' load all connectors '''
    for info in models.Connector.objects.order_by('priority').all():
        yield load_connector(info)


def load_connector(connector_info):
    ''' instantiate the connector class '''
    connector = importlib.import_module(
        'fedireads.connectors.%s' % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)
