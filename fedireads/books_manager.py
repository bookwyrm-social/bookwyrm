''' select and call a connector for whatever book task needs doing '''
from requests import HTTPError

import importlib
from urllib.parse import urlparse

from fedireads import models, settings
from fedireads.tasks import app


def get_or_create_book(remote_id):
    ''' pull up a book record by whatever means possible '''
    book = get_by_absolute_id(remote_id, models.Book)
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


def get_by_absolute_id(absolute_id, model):
    ''' generalized function to get from a model with a remote_id field '''
    if not absolute_id:
        return None

    # check if it's a remote status
    try:
        return model.objects.get(remote_id=absolute_id)
    except model.DoesNotExist:
        pass

    url = urlparse(absolute_id)
    if url.netloc != settings.DOMAIN:
        return None

    # try finding a local status with that id
    local_id = absolute_id.split('/')[-1]
    try:
        if hasattr(model.objects, 'select_subclasses'):
            possible_match = model.objects.select_subclasses().get(id=local_id)
        else:
            possible_match = model.objects.get(id=local_id)
    except model.DoesNotExist:
        return None

    # make sure it's not actually a remote status with an id that
    # clashes with a local id
    if possible_match.absolute_id == absolute_id:
        return possible_match
    return None


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
    connectors_info = models.Connector.objects.order_by('priority').all()
    return [load_connector(c) for c in connectors_info]


def load_connector(connector_info):
    ''' instantiate the connector class '''
    connector = importlib.import_module(
        'fedireads.connectors.%s' % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)
