''' handles all of the activity coming in to the server '''
from base64 import b64decode
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
import django.db.utils
from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
import json
import requests

from fedireads import models, outgoing
from fedireads import status as status_builder
from fedireads.remote_user import get_or_create_remote_user
from fedireads import tasks


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

    handlers = {
        'Follow': handle_follow,
        'Accept': handle_follow_accept,
        'Reject': handle_follow_reject,
        'Create': handle_create,
        'Like': handle_favorite,
        'Announce': handle_boost,
        'Add': {
            'Tag': handle_add,
        },
        'Undo': {
            'Follow': handle_unfollow,
            'Like': handle_unfavorite,
        },
        'Update': {
            'Person': None,# TODO: handle_update_user
            'Document': None# TODO: handle_update_book
        },
    }
    activity_type = activity['type']

    handler = handlers.get(activity_type, None)
    if isinstance(handler, dict):
        handler = handler.get(activity['object']['type'], None)

    if handler:
        return handler(activity)

    return HttpResponseNotFound()


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


def handle_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow
    to_follow = models.User.objects.get(actor=activity['object'])
    # figure out who they are
    user = get_or_create_remote_user(activity['actor'])
    try:
        request = models.UserFollowRequest.objects.create(
            user_subject=user,
            user_object=to_follow,
            relationship_id=activity['id']
        )
    except django.db.utils.IntegrityError as err:
        if err.__cause__.diag.constraint_name != 'userfollowrequest_unique':
            raise
        # Duplicate follow request. Not sure what the correct behaviour is, but
        # just dropping it works for now. We should perhaps generate the
        # Accept, but then do we need to match the activity id?
        return HttpResponse()

    if not to_follow.manually_approves_followers:
        status_builder.create_notification(
            to_follow,
            'FOLLOW',
            related_user=user
        )
        outgoing.handle_accept(user, to_follow, request)
    else:
        status_builder.create_notification(
            to_follow,
            'FOLLOW_REQUEST',
            related_user=user
        )
    return HttpResponse()


def handle_unfollow(activity):
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


def handle_follow_accept(activity):
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
    accepter.followers.add(requester)
    return HttpResponse()


def handle_follow_reject(activity):
    ''' someone is rejecting a follow request '''
    requester = models.User.objects.get(actor=activity['object']['actor'])
    rejecter = get_or_create_remote_user(activity['actor'])

    try:
        request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=rejecter
        )
        request.delete()
    except models.UserFollowRequest.DoesNotExist:
        pass

    return HttpResponse()

def handle_create(activity):
    ''' someone did something, good on them '''
    user = get_or_create_remote_user(activity['actor'])

    if not 'object' in activity:
        return HttpResponseBadRequest()

    if user.local:
        # we really oughtn't even be sending in this case
        return HttpResponse()

    if activity['object'].get('fedireadsType') in ['Review', 'Comment']  and \
            'inReplyToBook' in activity['object']:
        try:
            if activity['object']['fedireadsType'] == 'Review':
                builder = status_builder.create_review_from_activity
            else:
                builder = status_builder.create_comment_from_activity

            # create the status, it'll throw a valueerror if anything is missing
            builder(user, activity['object'])
        except ValueError:
            return HttpResponseBadRequest()
    else:
        # TODO: should only create notes if they are relevent to a book,
        # so, not every single thing someone posts on mastodon
        try:
            status = status_builder.create_status_from_activity(
                user,
                activity['object']
            )
            if status and status.reply_parent:
                status_builder.create_notification(
                    status.reply_parent.user,
                    'REPLY',
                    related_user=status.user,
                    related_status=status,
                )
        except ValueError:
            return HttpResponseBadRequest()

    return HttpResponse()


def handle_favorite(activity):
    ''' approval of your good good post '''
    print('hiii!')
    tasks.handle_incoming_favorite.delay(activity)
    return HttpResponse()


def handle_unfavorite(activity):
    ''' approval of your good good post '''
    favorite_id = activity['object']['id']
    fav = status_builder.get_favorite(favorite_id)
    if not fav:
        return HttpResponseNotFound()

    fav.delete()
    return HttpResponse()


def handle_boost(activity):
    ''' someone gave us a boost! '''
    try:
        status_id = activity['object'].split('/')[-1]
        status = models.Status.objects.get(id=status_id)
        booster = get_or_create_remote_user(activity['actor'])
    except (models.Status.DoesNotExist, models.User.DoesNotExist):
        return HttpResponseNotFound()

    if not booster.local:
        status_builder.create_boost_from_activity(booster, activity)

    status_builder.create_notification(
        status.user,
        'BOOST',
        related_user=booster,
        related_status=status,
    )

    return HttpResponse()

def handle_add(activity):
    ''' someone is tagging or shelving a book '''
    if activity['object']['type'] == 'Tag':
        user = get_or_create_remote_user(activity['actor'])
        if not user.local:
            book = activity['target']['id'].split('/')[-1]
            status_builder.create_tag(user, book, activity['object']['name'])
            return HttpResponse()
        return HttpResponse()
    return HttpResponseNotFound()

