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
        'Delete': handle_delete_status,
        'Like': handle_favorite,
        'Announce': handle_boost,
        'Add': {
            'Edition': handle_add,
            'Work': handle_add,
        },
        'Undo': {
            'Follow': handle_unfollow,
            'Like': handle_unfavorite,
            'Announce': handle_unboost,
        },
        'Update': {
            'Person': handle_update_user,
            'Edition': handle_update_book,
            'Work': handle_update_book,
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
    actor = get_or_create_remote_user(activity['actor'])
    try:
        relationship = models.UserFollowRequest.objects.create(
            user_subject=actor,
            user_object=to_follow,
            remote_id=activity['id']
        )
    except django.db.utils.IntegrityError as err:
        if err.__cause__.diag.constraint_name != 'userfollowrequest_unique':
            raise
        relationship = models.UserFollowRequest.objects.get(
            remote_id=activity['id']
        )
        # send the accept normally for a duplicate request

    if not to_follow.manually_approves_followers:
        status_builder.create_notification(
            to_follow,
            'FOLLOW',
            related_user=actor
        )
        outgoing.handle_accept(relationship)
    else:
        # Accept will be triggered manually
        status_builder.create_notification(
            to_follow,
            'FOLLOW_REQUEST',
            related_user=actor
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
    #raises models.UserFollowRequest.DoesNotExist


@app.task
def handle_create(activity):
    ''' someone did something, good on them '''
    if activity['object'].get('type') not in \
            ['Note', 'Comment', 'Quotation', 'Review', 'GeneratedNote']:
        # if it's an article or unknown type, ignore it
        return

    user = get_or_create_remote_user(activity['actor'])
    if user.local:
        # we really oughtn't even be sending in this case
        return

    # deduplicate incoming activities
    status_id = activity['object']['id']
    if models.Status.objects.filter(remote_id=status_id).count():
        return

    status = status_builder.create_status(activity['object'])
    if not status:
        return

    # create a notification if this is a reply
    if status.reply_parent and status.reply_parent.user.local:
        status_builder.create_notification(
            status.reply_parent.user,
            'REPLY',
            related_user=status.user,
            related_status=status,
        )


@app.task
def handle_delete_status(activity):
    ''' remove a status '''
    try:
        status_id = activity['object']['id']
    except TypeError:
        # this isn't a great fix, because you hit this when mastadon
        # is trying to delete a user.
        return
    try:
        status = models.Status.objects.select_subclasses().get(
            remote_id=status_id
        )
    except models.Status.DoesNotExist:
        return
    status_builder.delete_status(status)


@app.task
def handle_favorite(activity):
    ''' approval of your good good post '''
    fav = activitypub.Like(**activity)

    liker = get_or_create_remote_user(activity['actor'])
    if liker.local:
        return

    fav = fav.to_model(models.Favorite)

    status_builder.create_notification(
        fav.status.user,
        'FAVORITE',
        related_user=liker,
        related_status=fav.status,
    )


@app.task
def handle_unfavorite(activity):
    ''' approval of your good good post '''
    like = models.Favorite.objects.filter(
        remote_id=activity['object']['id']
    ).first()
    if not like:
        return
    like.delete()


@app.task
def handle_boost(activity):
    ''' someone gave us a boost! '''
    try:
        boost = activitypub.Boost(**activity).to_model(models.Boost)
    except activitypub.ActivitySerializerError:
        # this probably just means we tried to boost an unknown status
        return

    if not boost.user.local:
        status_builder.create_notification(
            boost.boosted_status.user,
            'BOOST',
            related_user=boost.user,
            related_status=boost.boosted_status,
        )


@app.task
def handle_unboost(activity):
    ''' someone gave us a boost! '''
    boost = models.Boost.objects.filter(
        remote_id=activity['object']['id']
    ).first()
    if boost:
        boost.delete()


@app.task
def handle_add(activity):
    ''' putting a book on a shelf '''
    # TODO absofuckinglutely not an acceptable solution
    if 'tag' in activity['id']:
        activitypub.AddBook(**activity).to_model(models.Tag)
    else:
        activitypub.AddBook(**activity).to_model(models.ShelfBook)


@app.task
def handle_update_user(activity):
    ''' receive an updated user Person activity object '''
    try:
        user = models.User.objects.get(remote_id=activity['object']['id'])
    except models.User.DoesNotExist:
        # who is this person? who cares
        return
    activitypub.Person(
        **activity['object']
    ).to_model(models.User, instance=user)
    # model save() happens in the to_model function


@app.task
def handle_update_book(activity):
    ''' a remote instance changed a book (Document) '''
    document = activity['object']
    # check if we have their copy and care about their updates
    book = models.Book.objects.select_subclasses().filter(
        remote_id=document['id'],
        sync=True,
    ).first()
    if not book:
        return

    books_manager.update_book(book, data=document)
