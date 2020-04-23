''' activitypub json for collections '''
from uuid import uuid4

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
            # TODO: document??
            'type': 'Document',
            'name': book.title,
            'url': book.absolute_id,
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.absolute_id,
        }
    }
