''' activitystream api '''
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads.settings import DOMAIN
from fedireads.openlibrary import get_or_create_book
from fedireads import models
from fedireads.api import get_or_create_remote_user
import json
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
def shared_inbox(request):
    ''' incoming activitypub events '''
    if request.method == 'GET':
        return HttpResponseNotFound()

    # TODO: RSA key verification

    try:
        activity = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return HttpResponseBadRequest

    if activity['type'] == 'Add':
        return handle_incoming_shelve(activity)

    if activity['type'] == 'Follow':
        return handle_incoming_follow(activity)

    if activity['type'] == 'Create':
        return handle_incoming_create(activity)

    return HttpResponse()


@csrf_exempt
def inbox(request, username):
    ''' incoming activitypub events '''
    if request.method == 'GET':
        return HttpResponseNotFound()

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
        'inbox': user.inbox,
        'followers': '%s/followers' % user.actor,
        'following': '%s/following' % user.actor,
        'summary': user.summary,
        'publicKey': {
            'id': '%s/#main-key' % user.actor,
            'owner': user.actor,
            'publicKeyPem': user.public_key,
        },
        'endpoints': {
            'sharedInbox': 'https://%s/inbox' % DOMAIN,
        }
    })


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
    to_follow = models.User.objects.get(actor=activity['object'])
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
