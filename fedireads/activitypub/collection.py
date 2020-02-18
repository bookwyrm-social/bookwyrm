''' activitypub json for collections '''
from uuid import uuid4
from urllib.parse import urlencode

from .status import get_status

def get_outbox(user, size):
    ''' helper function for creating an outbox '''
    return get_ordered_collection(user.outbox, size)


def get_outbox_page(user, page_id, statuses, max_id, min_id):
    ''' helper for formatting outbox pages '''
    # not generalizing this more because the format varies for some reason
    page = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': page_id,
        'type': 'OrderedCollectionPage',
        'partOf': user.outbox,
        'orderedItems': [],
    }

    for status in statuses:
        page['orderedItems'].append(get_status(status))

    if max_id:
        page['next'] = user.outbox + '?' + \
            urlencode({'min_id': max_id, 'page': 'true'})
    if min_id:
        page['prev'] = user.outbox + '?' + \
            urlencode({'max_id': min_id, 'page': 'true'})

    return page


def get_ordered_collection(path, size):
    ''' create an ordered collection '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': path,
        'type': 'OrderedCollection',
        'totalItems': size,
        'first': '%s?page=true' % path,
        'last': '%s?min_id=0&page=true' % path
    }


def get_add(*args):
    ''' activitypub Add activity '''
    return get_add_remove(*args, action='Add')


def get_remove(*args):
    ''' activitypub Add activity '''
    return get_add_remove(*args, action='Remove')


def get_add_remove(user, book, shelf, action='Add'):
    ''' format an Add or Remove json blob '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'type': action,
        'actor': user.actor,
        'object': {
            'type': 'Document',
            'name': book.data['title'],
            'url': book.openlibrary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.absolute_id,
        }
    }


