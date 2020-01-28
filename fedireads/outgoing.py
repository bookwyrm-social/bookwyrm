''' activitystream api '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads.settings import DOMAIN
from fedireads import models
from fedireads.api import get_or_create_remote_user
import json
import requests
from uuid import uuid4


def handle_account_search(query):
    ''' webfingerin' other servers '''
    domain = query.split('@')[1]
    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        response = requests.get(url)
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        for link in data['links']:
            if link['rel'] == 'self':
                user = get_or_create_remote_user(link['href'])
    return user


def handle_outgoing_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'summary': '',
        'type': 'Follow',
        'actor': user.actor,
        'object': to_follow.actor,
    }

    broadcast(user, activity, [to_follow.inbox])


def handle_response(response):
    ''' hopefully it's an accept from our follow request '''
    try:
        activity = response.json()
    except ValueError:
        return
    if activity['type'] == 'Accept':
        handle_incoming_accept(activity)

def handle_incoming_accept(activity):
    ''' someone is accepting a follow request '''
    # not actually a remote user so this is kinda janky
    user = get_or_create_remote_user(activity['actor'])
    # the person our local user wants to follow, who said yes
    followed = models.User.objects.get(actor=activity['object']['actor'])
    followed.followers.add(user)
    models.FollowActivity(
        uuid=activity['id'],
        user=user,
        followed=followed,
        content=activity,
    ).save()


def handle_shelve(user, book, shelf):
    ''' gettin organized '''
    # update the database
    models.ShelfBook(book=book, shelf=shelf, added_by=user).save()

    # send out the activitypub action
    summary = '%s marked %s as %s' % (
        user.username,
        book.data['title'],
        shelf.name
    )

    uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'summary': summary,
        'type': 'Add',
        'actor': user.actor,
        'object': {
            'type': 'Document',
            'name': book.data['title'],
            'url': book.openlibrary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.activitypub_id
        }
    }
    # TODO: this should be getting shared inboxes and deduplicating
    recipients = [u.inbox for u in user.followers.all()]

    models.ShelveActivity(
        uuid=uuid,
        user=user,
        content=activity,
        activity_type='Add',
        shelf=shelf,
        book=book,
    ).save()

    broadcast(user, activity, recipients)


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    review_uuid = uuid4()
    obj = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(review_uuid),
        'type': 'Article',
        'published': datetime.utcnow().isoformat(),
        'attributedTo': user.actor,
        'content': content,
        'inReplyTo': book.openlibrary_key,
        'rating': rating, # fedireads-only custom field
        'to': 'https://www.w3.org/ns/activitystreams#Public'
    }
    recipients = [u.inbox for u in user.followers.all()]
    create_uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': str(create_uuid),
        'type': 'Create',
        'actor': user.actor,

        'to': ['%s/followers' % user.actor],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': obj,

    }

    models.Review(
        uuid=create_uuid,
        user=user,
        content=activity,
        activity_type='Article',
        book=book,
        work=book.works.first(),
        name=name,
        rating=rating,
        review_content=content,
    ).save()
    broadcast(user, activity, recipients)


@csrf_exempt
def outbox(request, username):
    ''' outbox for the requested user '''
    user = models.User.objects.get(localname=username)
    size = models.Review.objects.filter(user=user).count()
    if request.method == 'GET':
        # list of activities
        return JsonResponse({
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': '%s/outbox' % user.actor,
            'type': 'OrderedCollection',
            'totalItems': size,
            'first': '%s/outbox?page=true' % user.actor,
            'last': '%s/outbox?min_id=0&page=true' % user.actor
        })
    # TODO: paginated list of messages

    #data = request.body.decode('utf-8')
    return HttpResponse()


def broadcast(sender, action, recipients):
    ''' send out an event to all followers '''
    for recipient in recipients:
        sign_and_send(sender, action, recipient)


def sign_and_send(sender, action, destination):
    ''' crpyto whatever and http junk '''
    inbox_fragment = sender.inbox.replace('https://%s' % DOMAIN, '')
    now = datetime.utcnow().isoformat()
    message_to_sign = '''(request-target): post %s
host: https://%s
date: %s''' % (inbox_fragment, DOMAIN, now)
    signer = pkcs1_15.new(RSA.import_key(sender.private_key))
    signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))

    signature = 'keyId="%s",' % sender.localname
    signature += 'headers="(request-target) host date",'
    signature += 'signature="%s"' % b64encode(signed_message)
    response = requests.post(
        destination,
        data=json.dumps(action),
        headers={
            'Date': now,
            'Signature': signature,
            'Host': DOMAIN,
        },
    )
    if not response.ok:
        response.raise_for_status()
    handle_response(response)
