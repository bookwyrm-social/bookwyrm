''' activitystream api '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads.settings import DOMAIN
from fedireads.openlibrary import get_or_create_book
from fedireads import models
import json
import requests
import re
from uuid import uuid4

def webfinger(request):
    ''' allow other servers to ask about a user '''
    resource = request.GET.get('resource')
    if not resource and not resource.startswith('acct:'):
        return HttpResponseBadRequest()
    ap_id = resource.replace('acct:', '')
    user = models.User.objects.filter(username=ap_id).first()
    if not user:
        return HttpResponseNotFound('No account found')
    return JsonResponse({
        'subject': 'acct:%s' % (user.username),
        'links': [
            {
                'rel': 'self',
                'type': 'application/activity+json',
                'href': user.actor
            }
        ]
    })


@csrf_exempt
def get_actor(request, username):
    ''' return an activitypub actor object '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    user = models.User.objects.get(localname=username)
    return JsonResponse({
        '@context': [
            'https://www.w3.org/ns/activitystreams',
            'https://w3id.org/security/v1'
        ],

        'id': user.actor,
        'type': 'Person',
        'preferredUsername': user.localname,
        'inbox': format_inbox(user),
        'followers': '%s/followers' % user.actor,
        'publicKey': {
            'id': '%s/#main-key' % user.actor,
            'owner': user.actor,
            'publicKeyPem': user.public_key,
        }
    })


@csrf_exempt
def inbox(request, username):
    ''' incoming activitypub events '''
    if request.method == 'GET':
        # TODO: return a collection of something?
        return JsonResponse({})

    # TODO: RSA key verification

    try:
        activity = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return HttpResponseBadRequest

    # TODO: should do some kind of checking if the user accepts
    # this action from the sender
    # but this will just throw an error if the user doesn't exist I guess
    models.User.objects.get(localname=username)

    if activity['type'] == 'Add':
        return handle_incoming_shelve(activity)

    if activity['type'] == 'Follow':
        return handle_incoming_follow(activity)

    if activity['type'] == 'Create':
        return handle_incoming_create(activity)
    return HttpResponse()


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


def handle_incoming_shelve(activity):
    ''' receiving an Add activity (to shelve a book) '''
    # TODO what happens here? If it's a remote over, then I think
    # I should save both the activity and the ShelfBook entry. But
    # I'll do that later.
    uuid = activity['id']
    models.ShelveActivity.objects.get(uuid=uuid)
    '''
    book_id = activity['object']['url']
    book = openlibrary.get_or_create_book(book_id)
    user_ap_id = activity['actor'].replace('https//:', '')
    user = models.User.objects.get(actor=user_ap_id)
    if not user or not user.local:
        return HttpResponseBadRequest()

    shelf = models.Shelf.objects.get(activitypub_id=activity['target']['id'])
    models.ShelfBook(
        shelf=shelf,
        book=book,
        added_by=user,
    ).save()
    '''
    return HttpResponse()



def handle_incoming_follow(activity):
    '''
    {
	"@context": "https://www.w3.org/ns/activitystreams",
	"id": "https://friend.camp/768222ce-a1c7-479c-a544-c93b8b67fb54",
	"type": "Follow",
	"actor": "https://friend.camp/users/tripofmice",
	"object": "https://ff2cb3e9.ngrok.io/api/u/mouse"
    }
    '''
    # figure out who they want to follow
    to_follow = re.sub(
        r'https?://([\w\.]+)/api/u/(\w+)',
        r'\2@\1',
        activity['object']
    )
    to_follow = models.User.objects.get(username=to_follow)
    # figure out who they are
    user = get_or_create_remote_user(activity['actor'])
    to_follow.followers.add(user)
    # verify uuid and accept the request
    models.FollowActivity(
        uuid=activity['id'],
        user=user,
        followed=to_follow,
        content=activity,
        activity_type='Follow',
    )
    uuid = uuid4()
    return JsonResponse({
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': 'https://%s/%s' % (DOMAIN, uuid),
        'type': 'Accept',
        'actor': user.actor,
        'object': activity,
    })


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

    broadcast(user, activity, [format_inbox(to_follow)])
    models.FollowActivity(
        uuid=uuid,
        user=user,
        followed=to_follow,
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
    recipients = [format_inbox(u) for u in user.followers.all()]

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
    recipients = [format_inbox(u) for u in user.followers.all()]
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


def handle_incoming_create(activity):
    ''' someone did something, good on them '''
    user = get_or_create_remote_user(activity['actor'])
    uuid = activity['id']
    # if it's an article and in reply to a book, we have a review
    if activity['object']['type'] == 'Article' and \
            'inReplyTo' in activity['object']:
        possible_book = activity['object']['inReplyTo']
        try:
            book = get_or_create_book(possible_book)
            models.Review(
                uuid=uuid,
                user=user,
                content=activity,
                activity_type='Article',
                book=book,
                work=book.works.first(),
                name=activity['object']['name'],
                rating=activity['object']['rating'],
                review_content=activity['objet']['content'],
            ).save()
            return HttpResponse()
        except KeyError:
            pass

    models.Activity(
        uuid=uuid,
        user=user,
        content=activity,
        activity_type=activity['object']['type']
    )
    return HttpResponse()

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
    inbox_fragment = '/api/u/%s/inbox' % (sender.localname)
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


def get_or_create_remote_user(actor):
    ''' wow, a foreigner '''
    try:
        user = models.User.objects.get(actor=actor)
    except models.User.DoesNotExist:
        # TODO: how do you actually correctly learn this?
        username = '%s@%s' % (actor.split('/')[-1], actor.split('/')[2])
        user = models.User.objects.create_user(
            username,
            '', '',
            actor=actor,
            local=False
        )
    return user


def format_inbox(user):
    ''' describe an inbox '''
    return '%s/inbox' % (user.actor)
