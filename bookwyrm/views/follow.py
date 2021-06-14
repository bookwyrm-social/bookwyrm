""" views for actions you can take in the application """
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_user_from_username


@login_required
@require_POST
def follow(request):
    """follow another user, here or abroad"""
    username = request.POST["user"]
    to_follow = get_user_from_username(request.user, username)

    try:
        models.UserFollowRequest.objects.create(
            user_subject=request.user,
            user_object=to_follow,
        )
    except IntegrityError:
        pass

    return redirect(to_follow.local_path)


@login_required
@require_POST
def unfollow(request):
    """unfollow a user"""
    username = request.POST["user"]
    to_unfollow = get_user_from_username(request.user, username)

    try:
        models.UserFollows.objects.get(
            user_subject=request.user, user_object=to_unfollow
        ).delete()
    except models.UserFollows.DoesNotExist:
        pass

    try:
        models.UserFollowRequest.objects.get(
            user_subject=request.user, user_object=to_unfollow
        ).delete()
    except models.UserFollowRequest.DoesNotExist:
        pass

    # this is handled with ajax so it shouldn't really matter
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def accept_follow_request(request):
    """a user accepts a follow request"""
    username = request.POST["user"]
    requester = get_user_from_username(request.user, username)

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester, user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        # Request already dealt with.
        return redirect(request.user.local_path)
    follow_request.accept()

    return redirect(request.user.local_path)


@login_required
@require_POST
def delete_follow_request(request):
    """a user rejects a follow request"""
    username = request.POST["user"]
    requester = get_user_from_username(request.user, username)

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester, user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        return HttpResponseBadRequest()

    follow_request.delete()
    return redirect("/user/%s" % request.user.localname)
