''' generates activitypub formatted objects '''
from uuid import uuid4
from fedireads.settings import DOMAIN


def shelve_action(user, book, shelf):
    ''' a user puts a book on a shelf.
    activitypub action type Add
    https://www.w3.org/ns/activitystreams#Add '''
    book_title = book.data['title']
    summary = '%s added %s to %s' % (
        user.username,
        book_title,
        shelf.name
    )
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'summary': summary,
        'type': 'Add',
        'actor': user.activitypub_id,
        'object': {
            'type': 'Document',
            'name': book_title,
            'url': book.openlibary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.activitypub_id
        }
    }


def accept_follow(activity, user):
    ''' say YES! to a user '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': 'https://%s/%s' % (DOMAIN, uuid),
        'type': 'Accept',
        'actor': user.actor['id'],
        'object': activity,
    }

