''' handles all of the activity coming in to the server '''
from base64 import b64decode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from uuid import uuid4

from fedireads import models
from fedireads.api import get_or_create_remote_user
from fedireads.openlibrary import get_or_create_book
from fedireads.settings import DOMAIN


# TODO: this should probably live somewhere else
class HttpResponseUnauthorized(HttpResponse):
    ''' http response for authentication failure '''
    status_code = 401


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
    # TODO: should this be functionally different from the non-shared inbox??
    if request.method == 'GET':
        return HttpResponseNotFound()

    try:
        activity = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return HttpResponseBadRequest

    # verify rsa signature
    signature_header = request.headers['Signature'].split(',')
    signature_dict = {}
    for pair in signature_header:
        k, v = pair.split('=', 1)
        v = v.replace('"', '')
        signature_dict[k] = v

    key_id = signature_dict['keyId']
    headers = signature_dict['headers']
    signature = b64decode(signature_dict['signature'])

    response = requests.get(
        key_id,
        headers={'Accept': 'application/activity+json'}
    )
    if not response.ok:
        return HttpResponseUnauthorized()

    actor = response.json()
    key = RSA.import_key(actor['publicKey']['publicKeyPem'])

    comparison_string = []
    for signed_header_name in headers.split(' '):
        if signed_header_name == '(request-target)':
            comparison_string.append('(request-target): post %s' % request.path)
        else:
            comparison_string.append('%s: %s' % (
                signed_header_name,
                request.headers[signed_header_name]
            ))
    comparison_string = '\n'.join(comparison_string)

    signer = pkcs1_15.new(key)
    digest = SHA256.new()
    digest.update(comparison_string.encode())
    try:
        signer.verify(digest, signature)
    except ValueError:
        return HttpResponseUnauthorized()

    if activity['type'] == 'Add':
        return handle_incoming_shelve(activity)

    if activity['type'] == 'Follow':
        return handle_incoming_follow(activity)

    if activity['type'] == 'Create':
        return handle_incoming_create(activity)

    return HttpResponseNotFound()


@csrf_exempt
def inbox(request, username):
    ''' incoming activitypub events '''
    # TODO: should do some kind of checking if the user accepts
    # this action from the sender probably? idk
    # but this will just throw an error if the user doesn't exist I guess
    models.User.objects.get(localname=username)

    return shared_inbox(request)


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
        'name': user.name,
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
            'sharedInbox': user.shared_inbox,
        }
    })


@csrf_exempt
def get_followers(request, username):
    ''' return a list of followers for an actor '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    user = models.User.objects.get(localname=username)
    followers = user.followers
    return format_follow_info(user, request.GET.get('page'), followers)


@csrf_exempt
def get_following(request, username):
    ''' return a list of following for an actor '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    user = models.User.objects.get(localname=username)
    following = models.User.objects.filter(followers=user)
    return format_follow_info(user, request.GET.get('page'), following)


def format_follow_info(user, page, follow_queryset):
    ''' create the activitypub json for followers/following '''
    id_slug = '%s/following' % user.actor
    if page:
        return JsonResponse(get_follow_page(follow_queryset, id_slug, page))
    count = follow_queryset.count()
    return JsonResponse({
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'OrderedCollection',
        'totalItems': count,
        'first': '%s?page=1' % id_slug,
    })

def get_follow_page(user_list, id_slug, page):
    ''' format a list of followers/following '''
    page = int(page)
    page_length = 10
    start = (page - 1) * page_length
    end = start + page_length
    follower_page = user_list.all()[start:end]
    data = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s?page=%d' % (id_slug, page),
        'type': 'OrderedCollectionPage',
        'totalItems': user_list.count(),
        'partOf': id_slug,
        'orderedItems': [u.actor for u in follower_page],
    }
    if end <= user_list.count():
        # there are still more pages
        data['next'] = '%s?page=%d' % (id_slug, page + 1)
    if start > 0:
        data['prev'] = '%s?page=%d' % (id_slug, page - 1)
    return data


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
    # TODO does this need to be signed?
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
            # TODO idk about this error handling, should probs be more granular
            book = get_or_create_book(possible_book)
            models.Review(
                uuid=uuid,
                user=user,
                content=activity,
                activity_type='Article',
                book=book,
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


def handle_incoming_accept(activity):
    ''' someone is accepting a follow request '''
    # our local user
    user = models.User.objects.get(actor=activity['actor'])
    # the person our local user wants to follow, who said yes
    followed = get_or_create_remote_user(activity['object']['actor'])

    # save this relationship in the db
    followed.followers.add(user)

    # save the activity record
    models.FollowActivity(
        uuid=activity['id'],
        user=user,
        followed=followed,
        content=activity,
    ).save()
    return HttpResponse()


def handle_response(response):
    ''' hopefully it's an accept from our follow request '''
    try:
        activity = response.json()
    except ValueError:
        return
    if activity['type'] == 'Accept':
        handle_incoming_accept(activity)


