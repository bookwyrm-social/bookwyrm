''' handles all of the activity coming in to the server '''
import json
from urllib.parse import urldefrag

import django.db.utils
from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import requests

from bookwyrm import activitypub, models, outgoing
from bookwyrm import status as status_builder
from bookwyrm.tasks import app
from bookwyrm.signatures import Signature


@csrf_exempt
@require_POST
def inbox(request, username):
    ''' incoming activitypub events '''
    try:
        models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    return shared_inbox(request)


@csrf_exempt
@require_POST
def shared_inbox(request):
    ''' incoming activitypub events '''
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
        },
        'Undo': {
            'Follow': handle_unfollow,
            'Like': handle_unfavorite,
            'Announce': handle_unboost,
        },
        'Update': {
            'Person': handle_update_user,
            'Edition': handle_update_edition,
            'Work': handle_update_work,
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

        remote_user = activitypub.resolve_remote_id(models.User, key_actor)
        if not remote_user:
            return False

        try:
            signature.verify(remote_user.key_pair.public_key, request)
        except ValueError:
            old_key = remote_user.key_pair.public_key
            remote_user = activitypub.resolve_remote_id(
                models.User, remote_user.remote_id, refresh=True
            )
            if remote_user.key_pair.public_key == old_key:
                raise # Key unchanged.
            signature.verify(remote_user.key_pair.public_key, request)
    except (ValueError, requests.exceptions.HTTPError):
        return False
    return True


@app.task
def handle_follow(activity):
    ''' someone wants to follow a local user '''
    try:
        relationship = activitypub.Follow(
            **activity
        ).to_model(models.UserFollowRequest)
    except django.db.utils.IntegrityError as err:
        if err.__cause__.diag.constraint_name != 'userfollowrequest_unique':
            raise
        relationship = models.UserFollowRequest.objects.get(
            remote_id=activity['id']
        )
        # send the accept normally for a duplicate request

    manually_approves = relationship.user_object.manually_approves_followers

    status_builder.create_notification(
        relationship.user_object,
        'FOLLOW_REQUEST' if manually_approves else 'FOLLOW',
        related_user=relationship.user_subject
    )
    if not manually_approves:
        outgoing.handle_accept(relationship)


@app.task
def handle_unfollow(activity):
    ''' unfollow a local user '''
    obj = activity['object']
    requester = activitypub.resolve_remote_id(models.User, obj['actor'])
    to_unfollow = models.User.objects.get(remote_id=obj['object'])
    # raises models.User.DoesNotExist

    to_unfollow.followers.remove(requester)


@app.task
def handle_follow_accept(activity):
    ''' hurray, someone remote accepted a follow request '''
    # figure out who they want to follow
    requester = models.User.objects.get(remote_id=activity['object']['actor'])
    # figure out who they are
    accepter = activitypub.resolve_remote_id(models.User, activity['actor'])

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
    rejecter = activitypub.resolve_remote_id(models.User, activity['actor'])

    request = models.UserFollowRequest.objects.get(
        user_subject=requester,
        user_object=rejecter
    )
    request.delete()
    #raises models.UserFollowRequest.DoesNotExist


@app.task
def handle_create(activity):
    ''' someone did something, good on them '''
    # deduplicate incoming activities
    activity = activity['object']
    status_id = activity['id']
    if models.Status.objects.filter(remote_id=status_id).count():
        return

    serializer = activitypub.activity_objects[activity['type']]
    activity = serializer(**activity)
    try:
        model = models.activity_models[activity.type]
    except KeyError:
        # not a type of status we are prepared to deserialize
        return

    status = activity.to_model(model)
    if not status:
        # it was discarded because it's not a bookwyrm type
        return

    # create a notification if this is a reply
    notified = []
    if status.reply_parent and status.reply_parent.user.local:
        notified.append(status.reply_parent.user)
        status_builder.create_notification(
            status.reply_parent.user,
            'REPLY',
            related_user=status.user,
            related_status=status,
        )
    if status.mention_users.exists():
        for mentioned_user in status.mention_users.all():
            if not mentioned_user.local or mentioned_user in notified:
                continue
            status_builder.create_notification(
                mentioned_user,
                'MENTION',
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
        status = models.Status.objects.get(
            remote_id=status_id
        )
    except models.Status.DoesNotExist:
        return
    models.Notification.objects.filter(related_status=status).all().delete()
    status_builder.delete_status(status)


@app.task
def handle_favorite(activity):
    ''' approval of your good good post '''
    fav = activitypub.Like(**activity)

    fav = fav.to_model(models.Favorite)
    if fav.user.local:
        return

    status_builder.create_notification(
        fav.status.user,
        'FAVORITE',
        related_user=fav.user,
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
    #this is janky as heck but I haven't thought of a better solution
    try:
        activitypub.AddBook(**activity).to_model(models.ShelfBook)
    except activitypub.ActivitySerializerError:
        activitypub.AddBook(**activity).to_model(models.Tag)


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
def handle_update_edition(activity):
    ''' a remote instance changed a book (Document) '''
    activitypub.Edition(**activity['object']).to_model(models.Edition)


@app.task
def handle_update_work(activity):
    ''' a remote instance changed a book (Document) '''
    activitypub.Work(**activity['object']).to_model(models.Work)
