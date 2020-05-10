''' handles all of the activity coming in to the server '''
import json
from base64 import b64decode
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
import django.db.utils
from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
import requests

from fedireads import books_manager, models, outgoing
from fedireads import status as status_builder
from fedireads.remote_user import get_or_create_remote_user
from fedireads.tasks import app


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

    if not activity.get('object'):
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
            'Tag': handle_tag,
        },
        'Undo': {
            'Follow': handle_unfollow,
            'Like': handle_unfavorite,
        },
        'Update': {
            'Person': None,# TODO: handle_update_user
            'Document': handle_update_book,
        },
    }
    activity_type = activity['type']

    handler = handlers.get(activity_type, None)
    if isinstance(handler, dict):
        handler = handler.get(activity['object']['type'], None)

    if not handler:
        return HttpResponseNotFound()

    handler.delay(activity)
    return HttpResponse()


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


@app.task
def handle_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow -- not using get_or_create because
    # we only allow you to follow local users
    try:
        to_follow = models.User.objects.get(actor=activity['object'])
    except models.User.DoesNotExist:
        return False
    # figure out who the actor is
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
        return

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


@app.task
def handle_unfollow(activity):
    ''' unfollow a local user '''
    obj = activity['object']
    try:
        requester = get_or_create_remote_user(obj['actor'])
        to_unfollow = models.User.objects.get(actor=obj['object'])
    except models.User.DoesNotExist:
        return False

    to_unfollow.followers.remove(requester)


@app.task
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


@app.task
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
        return False


@app.task
def handle_create(activity):
    ''' someone did something, good on them '''
    user = get_or_create_remote_user(activity['actor'])

    if user.local:
        # we really oughtn't even be sending in this case
        return True

    if activity['object'].get('fedireadsType') and \
            'inReplyToBook' in activity['object']:
        if activity['object']['fedireadsType'] == 'Review':
            builder = status_builder.create_review_from_activity
        elif activity['object']['fedireadsType'] == 'Quotation':
            builder = status_builder.create_quotation_from_activity
        else:
            builder = status_builder.create_comment_from_activity

        # create the status, it'll throw a ValueError if anything is missing
        builder(user, activity['object'])
    elif activity['object'].get('inReplyTo'):
        # only create the status if it's in reply to a status we already know
        if not status_builder.get_status(activity['object']['inReplyTo']):
            return True

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
    return True


@app.task
def handle_favorite(activity):
    ''' approval of your good good post '''
    try:
        status_id = activity['object'].split('/')[-1]
        status = models.Status.objects.get(id=status_id)
        liker = get_or_create_remote_user(activity['actor'])
    except (models.Status.DoesNotExist, models.User.DoesNotExist):
        return False

    if not liker.local:
        status_builder.create_favorite_from_activity(liker, activity)

    status_builder.create_notification(
        status.user,
        'FAVORITE',
        related_user=liker,
        related_status=status,
    )


@app.task
def handle_unfavorite(activity):
    ''' approval of your good good post '''
    favorite_id = activity['object']['id']
    fav = status_builder.get_favorite(favorite_id)
    if not fav:
        return False

    fav.delete()


@app.task
def handle_boost(activity):
    ''' someone gave us a boost! '''
    try:
        status_id = activity['object'].split('/')[-1]
        status = models.Status.objects.get(id=status_id)
        booster = get_or_create_remote_user(activity['actor'])
    except (models.Status.DoesNotExist, models.User.DoesNotExist):
        return False

    if not booster.local:
        status_builder.create_boost_from_activity(booster, activity)

    status_builder.create_notification(
        status.user,
        'BOOST',
        related_user=booster,
        related_status=status,
    )


@app.task
def handle_tag(activity):
    ''' someone is tagging a book '''
    user = get_or_create_remote_user(activity['actor'])
    if not user.local:
        book = activity['target']['id']
        status_builder.create_tag(user, book, activity['object']['name'])


@app.task
def handle_update_book(activity):
    ''' a remote instance changed a book (Document) '''
    document = activity['object']
    # check if we have their copy and care about their updates
    book = models.Book.objects.select_subclasses().filter(
        remote_id=document['url'],
        sync=True,
    ).first()
    if not book:
        return

    books_manager.update_book(book, data=document)
