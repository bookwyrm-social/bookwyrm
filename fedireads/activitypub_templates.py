''' generates activitypub formatted objects '''
from uuid import uuid4
from fedireads.settings import DOMAIN
from datetime import datetime

def outbox_collection(user, size):
    ''' outbox okay cool '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s/outbox' % user.actor,
        'type': 'OrderedCollection',
        'totalItems': size,
        'first': '%s/outbox?page=true' % user.actor,
        'last': '%s/outbox?min_id=0&page=true' % user.actor
    }

def shelve_activity(user, book, shelf):
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


def create_activity(user, obj):
    ''' wraps any object we're broadcasting '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': str(uuid),
        'type': 'Create',
        'actor': user.actor,

        'to': ['%s/followers' % user.actor],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': obj,

    }


def note_object(user, content):
    ''' a lil post '''
    uuid = uuid4()
    return {
        'id': str(uuid),
        'type': 'Note',
        'published': datetime.utcnow().isoformat(),
        'attributedTo': user.actor,
        'content': content,
        'to': 'https://www.w3.org/ns/activitystreams#Public'
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
        'inbox': inbox(user),
        'followers': '%s/followers' % user.actor,
        'publicKey': {
            'id': '%s/#main-key' % user.actor,
            'owner': user.actor,
            'publicKeyPem': user.public_key,
        }
    }


def inbox(user):
    ''' describe an inbox '''
    return '%s/inbox' % (user.actor)
