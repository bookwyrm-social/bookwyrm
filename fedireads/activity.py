''' Handle user activity '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from uuid import uuid4

from fedireads import models
from fedireads.openlibrary import get_or_create_book
from fedireads.sanitize_html import InputHtmlParser
from fedireads.settings import DOMAIN


def create_review(user, possible_book, name, content, rating):
    ''' a book review has been added '''
    # throws a value error if the book is not found
    book = get_or_create_book(possible_book)

    # sanitize review html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    # no ratings outside of 0-5
    rating = rating if 0 <= rating <= 5 else 0

    return models.Review.objects.create(
        user=user,
        book=book,
        name=name,
        rating=rating,
        content=content,
    )


def create_status(user, content, reply_parent=None, mention_books=None):
    ''' a status update '''
    # TODO: handle @'ing users

    # sanitize input html
    parser = InputHtmlParser()
    parser.feed(content)
    content = parser.get_output()

    status = models.Status.objects.create(
        user=user,
        content=content,
        reply_parent=reply_parent,
    )

    for book in mention_books:
        status.mention_books.add(book)

    return status


def get_status_json(status):
    ''' create activitypub json for a status '''
    user = status.user
    uri = 'https://%s/user/%s/status/%d' % (DOMAIN, user.localname, status.id)
    reply_parent_id = status.reply_parent.id if status.reply_parent else None
    status_json = {
        'id': uri,
        'url': uri,
        'inReplyTo': reply_parent_id,
        'published': status.created_date.isoformat(),
        'attributedTo': user.actor,
        # TODO: assuming all posts are public -- should check privacy db field
        'to': ['https://www.w3.org/ns/activitystreams#Public'],
        'cc': ['https://%s/user/%s/followers' % (DOMAIN, user.localname)],
        'sensitive': status.sensitive,
        'content': status.content,
        'type': status.activity_type,
        'fedireadsType': status.status_type,
        'attachment': [], # TODO: the book cover
        'replies': {
            'id': '%s/replies' % uri,
            'type': 'Collection',
            'first': {
                'type': 'CollectionPage',
                'next': '%s/replies?only_other_accounts=true&page=true' % uri,
                'partOf': '%s/replies' % uri,
                'items': [], # TODO: populate with replies
            }
        }
    }

    if status.status_type == 'Review':
        status_json['name'] = status.name,
        status_json['rating'] = status.rating
        status_json['fedireadsType'] = status.status_type

    return status_json


def get_create_json(user, status_json):
    ''' create activitypub json for a Create activity '''
    signer = pkcs1_15.new(RSA.import_key(user.private_key))
    content = status_json['content']
    signed_message = signer.sign(SHA256.new(content.encode('utf8')))
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': '%s/activity' % status_json['id'],
        'type': 'Create',
        'actor': user.actor,
        'published': status_json['published'],

        'to': ['%s/followers' % user.actor],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': status_json,
        'signature': {
            'type': 'RsaSignature2017',
            'creator': 'https://%s/user/%s#main-key' % (DOMAIN, user.localname),
            'created': status_json['published'],
            'signatureValue': b64encode(signed_message).decode('utf8'),
        }
    }



def get_add_json(*args):
    ''' activitypub Add activity '''
    return get_add_remove_json(*args, action='Add')


def get_remove_json(*args):
    ''' activitypub Add activity '''
    return get_add_remove_json(*args, action='Remove')


def get_add_remove_json(user, book, shelf, action='Add'):
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
            'id': 'https://%s/user/%s/shelf/%s' % \
                (DOMAIN, user.localname, shelf.identifier)
        }
    }


