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

    elif activity['type'] == 'Undo':
        response = handle_incoming_undo(activity)

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
def get_replies(request, username, status_id):
    ''' ordered collection of replies to a status '''
    # TODO: this isn't a full implmentation
    if request.method != 'GET':
        return HttpResponseBadRequest()

    status = models.Status.objects.get(id=status_id)
    if status.user.localname != username:
        return HttpResponseNotFound()

    replies = models.Status.objects.filter(
        reply_parent=status
    ).first()

    replies_activity = activitypub.get_replies(status, [replies])
    return JsonResponse(replies_activity)


@csrf_exempt
def get_followers(request, username):
    ''' return a list of followers for an actor '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    user = models.User.objects.get(localname=username)
    followers = user.followers
    page = request.GET.get('page')
    return JsonResponse(activitypub.get_followers(user, page, followers))


@csrf_exempt
def get_following(request, username):
    ''' return a list of following for an actor '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    user = models.User.objects.get(localname=username)
    following = models.User.objects.filter(followers=user)
    page = request.GET.get('page')
    return JsonResponse(activitypub.get_following(user, page, following))


def handle_incoming_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow
    to_follow = models.User.objects.get(actor=activity['object'])
    # figure out who they are
    user = get_or_create_remote_user(activity['actor'])
    # TODO: allow users to manually approve requests
    models.UserRelationship.objects.create(
        user_subject=to_follow,
        user_object=user,
        status='follow_request',
        relationship_id=activity['id']
    )
    outgoing.handle_outgoing_accept(user, to_follow, activity)
    return HttpResponse()


def handle_incoming_undo(activity):
    ''' unfollow a local user '''
    obj = activity['object']
    if not obj['type'] == 'Follow':
        #idk how to undo other things
        return HttpResponseNotFound()
    try:
        requester = get_or_create_remote_user(obj['actor'])
        to_unfollow = models.User.objects.get(actor=obj['object'])
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    to_unfollow.followers.remove(requester)
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

    # TODO: should only create notes if they are relevent to a book,
    # so, not every single thing someone posts on mastodon
    response = HttpResponse()
    content = activity['object'].get('content')
    if activity['object'].get('fedireadsType') == 'Review' and \
            'inReplyToBook' in activity['object']:
        book = activity['object']['inReplyToBook']
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

