''' views for actions you can take in the application '''
from django.db import  transaction
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_user_from_username

@login_required
@require_POST
def follow(request):
    ''' follow another user, here or abroad '''
    username = request.POST['user']
    try:
        to_follow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    models.UserFollowRequest.objects.get_or_create(
        user_subject=request.user,
        user_object=to_follow,
    )
    return redirect(to_follow.local_path)


@login_required
@require_POST
def unfollow(request):
    ''' unfollow a user '''
    username = request.POST['user']
    try:
        to_unfollow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    models.UserFollows.objects.get(
        user_subject=request.user,
        user_object=to_unfollow
    )

    to_unfollow.followers.remove(request.user)
    return redirect(to_unfollow.local_path)


@login_required
@require_POST
def accept_follow_request(request):
    ''' a user accepts a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        # Request already dealt with.
        return redirect(request.user.local_path)
    handle_accept(follow_request)

    return redirect(request.user.local_path)


def handle_accept(follow_request):
    ''' send an acceptance message to a follow request '''
    with transaction.atomic():
        relationship = models.UserFollows.from_request(follow_request)
        follow_request.delete()
        relationship.save()


@login_required
@require_POST
def delete_follow_request(request):
    ''' a user rejects a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        return HttpResponseBadRequest()

    follow_request.delete()
    return redirect('/user/%s' % request.user.localname)
