''' handles all of the activity coming in to the server '''
from base64 import b64decode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import django.db.utils
from django.db.models import Q
import json
import requests

from fedireads import activitypub
from fedireads import models
from fedireads import outgoing
from fedireads.status import create_review_from_activity, \
    create_status_from_activity, create_tag, create_notification
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

    elif activity['type'] == 'Like':
        response = handle_incoming_favorite(activity)

    elif activity['type'] == 'Add':
        response = handle_incoming_add(activity)
    elif activity['type'] == 'Reject':
        response = handle_incoming_follow_reject(activity)

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
    # but this will just throw a 404 if the user doesn't exist
    try:
        models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    return shared_inbox(request)


def handle_incoming_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow
    to_follow = models.User.objects.get(actor=activity['object'])
    # figure out who they are
    user = get_or_create_remote_user(activity['actor'])
    # TODO: allow users to manually approve requests
    try:
        request = models.UserFollowRequest.objects.create(
            user_subject=user,
            user_object=to_follow,
            relationship_id=activity['id']
        )
    except django.db.utils.IntegrityError:
        # Duplicate follow request. Not sure what the correct behaviour is, but
        # just dropping it works for now. We should perhaps generate the
        # Accept, but then do we need to match the activity id?
        return HttpResponse()

    if not to_follow.manually_approves_followers:
        create_notification(to_follow, 'FOLLOW', related_user=user)
        outgoing.handle_outgoing_accept(user, to_follow, request)
    else:
        create_notification(to_follow, 'FOLLOW_REQUEST', related_user=user)
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

    try:
        request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=accepter
        )
        request.delete()
    except models.UserFollowRequest.DoesNotExist:
        pass
    else:
        accepter.followers.add(requester)
    return HttpResponse()


def handle_incoming_follow_reject(activity):
    ''' someone is rejecting a follow request '''
    requester = models.User.objects.get(actor=activity['object']['actor'])
    rejecter = get_or_create_remote_user(activity['actor'])

    try:
        request = models.UserFollowRequest.objects.get(user_subject=requester, user_object=rejecter)
        request.delete()
    except models.UserFollowRequest.DoesNotExist:
        pass

    return HttpResponse()

def handle_incoming_create(activity):
    ''' someone did something, good on them '''
    user = get_or_create_remote_user(activity['actor'])

    if not 'object' in activity:
        return HttpResponseBadRequest()

    # TODO: should only create notes if they are relevent to a book,
    # so, not every single thing someone posts on mastodon
    response = HttpResponse()
    if activity['object'].get('fedireadsType') == 'Review' and \
            'inReplyToBook' in activity['object']:
        if user.local:
            review_id = activity['object']['id'].split('/')[-1]
            models.Review.objects.get(id=review_id)
        else:
            try:
                create_review_from_activity(user, activity['object'])
            except ValueError:
                return HttpResponseBadRequest()
    elif not user.local:
        try:
            status = create_status_from_activity(user, activity['object'])
            if status and status.reply_parent:
                create_notification(
                    status.reply_parent.user,
                    'REPLY',
                    related_user=status.user,
                    related_status=status,
                )
        except ValueError:
            return HttpResponseBadRequest()

    return response


def handle_incoming_favorite(activity):
    ''' approval of your good good post '''
    try:
        status_id = activity['object'].split('/')[-1]
        status = models.Status.objects.get(id=status_id)
        liker = get_or_create_remote_user(activity['actor'])
    except (models.Status.DoesNotExist, models.User.DoesNotExist):
        return HttpResponseNotFound()

    if not liker.local:
        status.favorites.add(liker)

    create_notification(
        status.user,
        'FAVORITE',
        related_user=liker,
        related_status=status,
    )
    return HttpResponse()


def handle_incoming_add(activity):
    ''' someone is tagging or shelving a book '''
    if activity['object']['type'] == 'Tag':
        user = get_or_create_remote_user(activity['actor'])
        if not user.local:
            book = activity['target']['id'].split('/')[-1]
            create_tag(user, book, activity['object']['name'])
            return HttpResponse()
        return HttpResponse()
    return HttpResponseNotFound()
