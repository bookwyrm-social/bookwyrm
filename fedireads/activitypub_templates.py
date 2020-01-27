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
        'actor': user.actor,
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

def follow_request(user, follow):
    ''' ask to be friends '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'summary': '',
        'type': 'Follow',
        'actor': user.actor,
        'object': follow,
    }


def accept_follow(activity, user):
    ''' say YES! to a user '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': 'https://%s/%s' % (DOMAIN, uuid),
        'type': 'Accept',
        'actor': user.actor,
        'object': activity,
    }


def actor(user):
    ''' format an actor object from a user '''
    return {
        '@context': [
            'https://www.w3.org/ns/activitystreams',
            'https://w3id.org/security/v1'
        ],

        'id': user.actor,
        'type': 'Person',
        'preferredUsername': user.username,
        'inbox': 'https://%s/api/%s/inbox' % (DOMAIN, user.username),
        'followers': 'https://%s/api/u/%s/followers' % \
                (DOMAIN, user.username),
        'publicKey': {
            'id': 'https://%s/api/u/%s#main-key' % (DOMAIN, user.username),
            'owner': 'https://%s/api/u/%s' % (DOMAIN, user.username),
            'publicKeyPem': user.public_key,
        }
    }


def inbox(user):
    ''' describe an inbox '''
    return 'https://%s/api/%s/inbox' % (DOMAIN, user.username)
