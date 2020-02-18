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

from fedireads import activitypub
from fedireads import models
from fedireads import outgoing
from fedireads.status import create_review, create_status
from fedireads.remote_user import get_or_create_remote_user


@csrf_exempt
def shared_inbox(request):
    ''' incoming activitypub events '''
    # TODO: should this be functionally different from the non-shared inbox??
    if request.method == 'GET':
        return HttpResponseNotFound()

    try:
        activity = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return HttpResponseBadRequest()

    try:
        verify_signature(request)
    except ValueError:
        return HttpResponse(status=401)

    response = HttpResponseNotFound()
    if activity['type'] == 'Follow':
        response = handle_incoming_follow(activity)

    elif activity['type'] == 'Create':
        response = handle_incoming_create(activity)

    elif activity['type'] == 'Accept':
        response = handle_incoming_follow_accept(activity)

    # TODO: Add, Undo, Remove, etc

    return response


def verify_signature(request):
    ''' verify rsa signature '''
    signature_dict = {}
    for pair in request.headers['Signature'].split(','):
        k, v = pair.split('=', 1)
        v = v.replace('"', '')
        signature_dict[k] = v

    try:
        key_id = signature_dict['keyId']
        headers = signature_dict['headers']
        signature = b64decode(signature_dict['signature'])
    except KeyError:
        raise ValueError('Invalid auth header')

    response = requests.get(
        key_id,
        headers={'Accept': 'application/activity+json'}
    )
    if not response.ok:
        raise ValueError('Could not load public key')

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

    # raises a ValueError if it fails
    signer.verify(digest, signature)

    return True


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
    return JsonResponse(activitypub.get_actor(user))


@csrf_exempt
def get_status(request, username, status_id):
    ''' return activity json for a specific status '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    try:
        user = models.User.objects.get(localname=username)
        status = models.Status.objects.get(id=status_id)
    except ValueError:
        return HttpResponseNotFound()

    if user != status.user:
        return HttpResponseNotFound()

    return JsonResponse(activitypub.get_status(status))


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


def handle_incoming_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow
    to_follow = models.User.objects.get(actor=activity['object'])
    # figure out who they are
    user = get_or_create_remote_user(activity['actor'])
    # TODO: allow users to manually approve requests
    outgoing.handle_outgoing_accept(user, to_follow, activity)
    return HttpResponse()


def handle_incoming_follow_accept(activity):
    ''' hurray, someone remote accepted a follow request '''
    # figure out who they want to follow
    requester = models.User.objects.get(actor=activity['object']['actor'])
    # figure out who they are
    accepter = get_or_create_remote_user(activity['actor'])

    accepter.followers.add(requester)
    return HttpResponse()


def handle_incoming_create(activity):
    ''' someone did something, good on them '''
    user = get_or_create_remote_user(activity['actor'])

    if not 'object' in activity:
        return HttpResponseBadRequest()

    response = HttpResponse()
    content = activity['object'].get('content')
    if activity['object'].get('fedireadsType') == 'Review' and \
            'inReplyTo' in activity['object']:
        book = activity['object']['inReplyTo']
        book = book.split('/')[-1]
        name = activity['object'].get('name')
        rating = activity['object'].get('rating')
        if user.local:
            review_id = activity['object']['id'].split('/')[-1]
            models.Review.objects.get(id=review_id)
        else:
            try:
                create_review(user, book, name, content, rating)
            except ValueError:
                return HttpResponseBadRequest()
    elif not user.local:
        try:
            create_status(user, content)
        except ValueError:
            return HttpResponseBadRequest()

    return response


def handle_incoming_accept(activity):
    ''' someone is accepting a follow request '''
    # our local user
    user = models.User.objects.get(actor=activity['actor'])
    # the person our local user wants to follow, who said yes
    followed = get_or_create_remote_user(activity['object']['actor'])

    # save this relationship in the db
    followed.followers.add(user)

    return HttpResponse()

