''' handles all of the activity coming in to the server '''
import json
from urllib.parse import urldefrag

import django.db.utils
from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
import requests

from bookwyrm import activitypub, books_manager, models, outgoing
from bookwyrm import status as status_builder
from bookwyrm.remote_user import get_or_create_remote_user, refresh_remote_user
from bookwyrm.tasks import app
from bookwyrm.signatures import Signature


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
        resp = request.body
        activity = json.loads(resp)
        if isinstance(activity, str):
            activity = json.loads(activity)
        activity_object = activity['object']
    except (json.decoder.JSONDecodeError, KeyError):
        return HttpResponseBadRequest()

    if not has_valid_signature(request, activity):
        if activity['type'] == 'Delete':
            # Pretend that unauth'd deletes succeed. Auth may be failing because
            # the resource or owner of the resource might have been deleted.
            return HttpResponse()
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
        handler = handler.get(activity_object['type'], None)

    if not handler:
        return HttpResponseNotFound()

    handler.delay(activity)
    return HttpResponse()


def has_valid_signature(request, activity):
    ''' verify incoming signature '''
    try:
        signature = Signature.parse(request)

        key_actor = urldefrag(signature.key_id).url
        if key_actor != activity.get('actor'):
            raise ValueError("Wrong actor created signature.")

        remote_user = get_or_create_remote_user(key_actor)

        try:
            signature.verify(remote_user.public_key, request)
        except ValueError:
            old_key = remote_user.public_key
            refresh_remote_user(remote_user)
            if remote_user.public_key == old_key:
                raise # Key unchanged.
            signature.verify(remote_user.public_key, request)
    except (ValueError, requests.exceptions.HTTPError):
        return False
    return True


@app.task
def handle_follow(activity):
    ''' someone wants to follow a local user '''
    # figure out who they want to follow -- not using get_or_create because
    # we only care if you want to follow local users
    try:
        to_follow = models.User.objects.get(remote_id=activity['object'])
    except models.User.DoesNotExist:
        # some rando, who cares
        return
    if not to_follow.local:
        # just ignore follow alerts about other servers. maybe they should be
        # handled. maybe they shouldn't be sent at all.
        return

    # figure out who the actor is
    user = get_or_create_remote_user(activity['actor'])
    try:
        relationship = models.UserFollowRequest.objects.create(
            user_subject=user,
            user_object=to_follow,
            remote_id=activity['id']
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
        outgoing.handle_accept(user, to_follow, relationship)
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
    requester = get_or_create_remote_user(obj['actor'])
    to_unfollow = models.User.objects.get(remote_id=obj['object'])
    # raises models.User.DoesNotExist

    to_unfollow.followers.remove(requester)


@app.task
def handle_follow_accept(activity):
    ''' hurray, someone remote accepted a follow request '''
    # figure out who they want to follow
    requester = models.User.objects.get(remote_id=activity['object']['actor'])
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
    requester = models.User.objects.get(remote_id=activity['object']['actor'])
    rejecter = get_or_create_remote_user(activity['actor'])

    request = models.UserFollowRequest.objects.get(
        user_subject=requester,
        user_object=rejecter
    )
    request.delete()
    #raises models.UserFollowRequest.DoesNotExist:


@app.task
def handle_create(activity):
    ''' someone did something, good on them '''
    if activity['object'].get('type') not in \
            ['Note', 'Comment', 'Quotation', 'Review']:
        # if it's an article or unknown type, ignore it
        return

    user = get_or_create_remote_user(activity['actor'])
    if user.local:
        # we really oughtn't even be sending in this case
        return

    # render the json into an activity object
    serializer = activitypub.activity_objects[activity['object']['type']]
    activity = serializer(**activity['object'])

    # ignore notes that aren't replies to known statuses
    if activity.type == 'Note':
        reply = models.Status.objects.filter(
            remote_id=activity.inReplyTo
        ).first()
        if not reply:
            return

    model = models.activity_models[activity.type]
    status = activity.to_model(model)

    # create a notification if this is a reply
    if status.reply_parent and status.reply_parent.user.local:
        status_builder.create_notification(
            status.reply_parent.user,
            'REPLY',
            related_user=status.user,
            related_status=status,
        )


@app.task
def handle_favorite(activity):
    ''' approval of your good good post '''
    fav = activitypub.Like(**activity['object'])
    # raises ValueError in to_model if a foreign key could not be resolved in

    liker = get_or_create_remote_user(activity['actor'])
    if liker.local:
        return

    status = fav.to_model(models.Favorite)

    status_builder.create_notification(
        status.user,
        'FAVORITE',
        related_user=liker,
        related_status=status,
    )


@app.task
def handle_unfavorite(activity):
    ''' approval of your good good post '''
    like = activitypub.Like(**activity['object'])
    fav = models.Favorite.objects.filter(remote_id=like.id).first()

    fav.delete()


@app.task
def handle_boost(activity):
    ''' someone gave us a boost! '''
    status_id = activity['object'].split('/')[-1]
    status = models.Status.objects.get(id=status_id)
    booster = get_or_create_remote_user(activity['actor'])

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
